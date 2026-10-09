"""Fresh, separately versioned Market Atlas quantitative research snapshot.

Run: python market_models/ai_quant.py
The original 2026-09-29 reports and source snapshots are never modified.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import sys
import urllib.parse
import urllib.request
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Use the standard Python installation. OneDrive-local compiled package DLLs
# are blocked by this device's Application Control; no policy is altered.
import numpy as np
from scipy.stats import binomtest, kurtosis, norm, skew
from threadpoolctl import threadpool_limits

from fetch_data import session_date
from models import FEATURE_START, descriptive, features, kalman_beta, predict_at, scenarios, volatility
from visual_scenarios import visual_scenarios

START = '2016-09-30'
CUTOFF = '2026-09-30'
DATA = ROOT / 'data' / CUTOFF / 'quant-refresh'
RESULT = ROOT / 'results' / CUTOFF / 'quant-refresh.json'
MODELS = ('ridge', 'ols', 'knn50', 'mean', 'zero', 'gbm', 'ar1')
IMPLEMENTATIONS = {
    'gbm': {'implementation': 'Interpreted NumPy histogram gradient boosted regression stumps; squared-error objective.',
            'rounds': 80, 'learning_rate': .05, 'min_leaf': 40, 'l2': 10, 'bins': 32,
            'adaptation': 'Uses fixed shallow stumps rather than the archived sklearn depth3 implementation because compiled sklearn DLLs are blocked by device Application Control. No security policy is changed.'},
    'hmm': {'implementation': 'Interpreted NumPy / SciPy two-state Gaussian EM with scaled forward/backward training; only forward filtering on evaluation records.',
            'states': 2, 'fixed_starts': [7, 29], 'max_iterations': 100, 'likelihood_tolerance': .001,
            'variance_floor_percent_squared': .001, 'refit_every': 126,
            'adaptation': 'EM uses historical training data only; the archived hmmlearn compiled implementation is replaced by auditable interpreted calculations.'}}
CONFIG = {'horizons': [5, 20], 'minimum_training_labels': 756,
          'ridge_alpha': 10., 'knn_neighbors': 50, 'seed': 20260930}
STOCKS = [('nvda', 'NVDA', 'Nvidia'), ('tsm', 'TSM', 'TSMC ADR'),
          ('intc', 'INTC', 'Intel'), ('amd', 'AMD', 'Advanced Micro Devices'),
          ('mu', 'MU', 'Micron'), ('avgo', 'AVGO', 'Broadcom'),
          ('etn', 'ETN', 'Eaton'), ('vrt', 'VRT', 'Vertiv'),
          ('alab', 'ALAB', 'Astera Labs'), ('crdo', 'CRDO', 'Credo')]
ASSETS = [dict(id=i, symbol=s, name=n, currency='USD', timezone='America/New_York',
               instrument='US-listed TSMC ADR' if i == 'tsm' else 'US-listed common stock',
               price_field='adjusted_close') for i, s, n in STOCKS]
ASSETS += [dict(id=i, symbol=s, name=n, currency=c, timezone=z,
                instrument='Price index; not a directly purchasable security', price_field='close')
           for i, s, n, c, z in [('sp500', '^GSPC', 'S&P 500', 'USD', 'America/New_York'),
                                ('nasdaq', '^IXIC', 'Nasdaq Composite', 'USD', 'America/New_York'),
                                ('ihsg', '^JKSE', 'IHSG', 'IDR', 'Asia/Jakarta')]]
BENCHMARK = dict(id='spy', symbol='SPY', name='SPDR S&P 500 ETF', currency='USD',
                 timezone='America/New_York', instrument='Benchmark ETF', price_field='adjusted_close')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def relative(path):
    return str(path.relative_to(ROOT.parent)).replace('\\', '/')


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,*/*'})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()


def acquire(item):
    """Retain raw response first, then validate a non-synthetic daily source CSV."""
    start = int(dt.datetime.fromisoformat(START).replace(tzinfo=dt.timezone.utc).timestamp())
    end = int((dt.datetime.fromisoformat(CUTOFF) + dt.timedelta(days=1)).replace(tzinfo=dt.timezone.utc).timestamp())
    url = ('https://query1.finance.yahoo.com/v8/finance/chart/' + urllib.parse.quote(item['symbol'], safe='') +
           f'?period1={start}&period2={end}&interval=1d&events=div%2Csplits')
    raw_path, csv_path = DATA / (item['id'] + '-raw.json'), DATA / (item['id'] + '.csv')
    retained = raw_path.exists()
    if not retained:
        raw = fetch(url)
        payload = json.loads(raw)
        if payload.get('chart', {}).get('error') or not payload.get('chart', {}).get('result'):
            raise ValueError(f"{item['id']}: provider chart error")
        raw_path.write_bytes(raw)
    raw = raw_path.read_bytes()
    chart = json.loads(raw)['chart']['result'][0]
    quote = chart['indicators']['quote'][0]
    adj = chart['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
    rows, dropped = [], []
    for i, stamp in enumerate(chart.get('timestamp', [])):
        date = session_date(stamp, item['timezone'])
        if not START <= date <= CUTOFF:
            continue
        values = {key: quote.get(key, [None] * len(chart['timestamp']))[i]
                  for key in ('open', 'high', 'low', 'close', 'volume')}
        if any(values[k] is None for k in ('open', 'high', 'low', 'close')):
            dropped.append(date)
            continue
        if not all(math.isfinite(values[k]) and values[k] > 0 for k in ('open', 'high', 'low', 'close')):
            raise ValueError(f"{item['id']}: invalid OHLC on {date}")
        if values['low'] > values['high']:
            raise ValueError(f"{item['id']}: reversed low/high on {date}")
        adjusted = adj[i] if len(adj) > i else None
        if item['price_field'] == 'adjusted_close' and (adjusted is None or not math.isfinite(adjusted) or adjusted <= 0):
            raise ValueError(f"{item['id']}: absent adjusted close on {date}")
        rows.append(dict(date=date, **values, adjusted_close=adjusted if adjusted else values['close']))
    dates = [r['date'] for r in rows]
    if dates != sorted(set(dates)) or len(rows) < FEATURE_START + 252 + 26:
        raise ValueError(f"{item['id']}: insufficient or unordered daily history ({len(rows)})")
    if dates[-1] != CUTOFF:
        raise ValueError(f"{item['id']}: latest completed source date {dates[-1]} is not cutoff {CUTOFF}")
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = stream.getvalue().encode('utf-8')
    if csv_path.exists() and csv_path.read_bytes() != csv_bytes:
        raise ValueError(f"{item['id']}: existing immutable CSV differs from retained raw source")
    if not csv_path.exists():
        csv_path.write_bytes(csv_bytes)
    meta = dict(item, url=url, raw_file=relative(raw_path), csv_file=relative(csv_path),
                raw_sha256=hashlib.sha256(raw).hexdigest(), csv_sha256=hashlib.sha256(csv_bytes).hexdigest(),
                rows=len(rows), first=dates[0], last=dates[-1], dropped_null_ohlc_dates=dropped,
                provider_meta=chart['meta'], acquisition='retained_response' if retained else 'fresh_response',
                definition='Provider adjusted-close return proxy; raw close retained separately.'
                if item['price_field'] == 'adjusted_close' else 'Price-index close; excludes dividend reinvestment.')
    return meta


def load_series(meta):
    with (ROOT.parent / meta['csv_file']).open(encoding='utf-8', newline='') as stream:
        raw = list(csv.DictReader(stream))
    dates = [r['date'] for r in raw]
    p = np.array([float(r[meta['price_field']]) for r in raw])
    return dates, p, raw


def gbm():
    return HistogramStumpBoosting(rounds=80, learning_rate=.05, min_leaf=40, l2=10, bins=32)


class HistogramStumpBoosting:
    """Fixed squared-loss gradient boosting using histogram regression stumps.

    This interpreted adaptation avoids blocked compiled sklearn components.
    It is deliberately identified separately from the archived depth3 GBM.
    All feature thresholds and leaf values come only from the passed training set.
    """
    def __init__(self, rounds=80, learning_rate=.05, min_leaf=40, l2=10., bins=32):
        self.rounds, self.learning_rate, self.min_leaf, self.l2, self.bins = rounds, learning_rate, min_leaf, l2, bins

    def fit(self, x, y):
        x, y = np.asarray(x), np.asarray(y)
        self.intercept = float(y.mean())
        self.thresholds = [np.unique(np.quantile(x[:, j], np.linspace(0, 1, self.bins+1)[1:-1]))
                           for j in range(x.shape[1])]
        binned = [np.searchsorted(t, x[:, j], side='left') for j, t in enumerate(self.thresholds)]
        counts = [np.bincount(b, minlength=len(t)+1) for b, t in zip(binned, self.thresholds)]
        cumulative_count = [np.cumsum(c)[:-1] for c in counts]
        prediction = np.full(len(y), self.intercept)
        self.trees = []
        for _ in range(self.rounds):
            residual = y-prediction
            total = float(residual.sum())
            best = None
            for j, (b, c, threshold, left_n) in enumerate(zip(binned, counts, self.thresholds, cumulative_count)):
                if not len(threshold):
                    continue
                left_s = np.cumsum(np.bincount(b, weights=residual, minlength=len(c)))[:-1]
                right_n, right_s = len(y)-left_n, total-left_s
                valid = (left_n >= self.min_leaf) & (right_n >= self.min_leaf)
                gain = left_s**2/(left_n+self.l2)+right_s**2/(right_n+self.l2)-total**2/(len(y)+self.l2)
                gain = np.where(valid, gain, -np.inf)
                split = int(np.argmax(gain))
                if math.isfinite(gain[split]) and gain[split] > 1e-14 and (best is None or gain[split] > best[0]):
                    best = (float(gain[split]), j, split, float(left_s[split]/(left_n[split]+self.l2)),
                            float(right_s[split]/(right_n[split]+self.l2)))
            if best is None:
                break
            _, j, split, left, right = best
            threshold = float(self.thresholds[j][split])
            self.trees.append((j, threshold, left, right))
            prediction += self.learning_rate*np.where(x[:, j] <= threshold, left, right)
        return self

    def predict(self, x):
        x = np.asarray(x)
        result = np.full(len(x), self.intercept)
        for j, threshold, left, right in self.trees:
            result += self.learning_rate*np.where(x[:, j] <= threshold, left, right)
        return result


class GaussianHMM:
    """Two Gaussian states fitted by scaled forward/backward EM.

    EM is used only on the historical training window. Dashboard probability
    records are separately filtered forward, never backward smoothed.
    """
    def __init__(self, n_components=2, covariance_type='diag', n_iter=100, tol=.001,
                 random_state=7, min_covar=.001):
        assert n_components == 2 and covariance_type == 'diag'
        self.n_iter, self.tol, self.random_state, self.min_covar = n_iter, tol, random_state, min_covar

    def _forward(self, values):
        emission = np.exp(norm.logpdf(values[:, None], self.means_.ravel(), np.sqrt(self.covars_.ravel())))
        emission = np.maximum(emission, 1e-300)
        alpha = np.empty((len(values), 2))
        scales = np.empty(len(values))
        alpha[0] = self.startprob_*emission[0]
        scales[0] = alpha[0].sum()
        alpha[0] /= scales[0]
        for t in range(1, len(values)):
            alpha[t] = (alpha[t-1]@self.transmat_)*emission[t]
            scales[t] = alpha[t].sum()
            alpha[t] /= scales[t]
        return alpha, scales, emission

    def fit(self, sample):
        from types import SimpleNamespace
        values = np.asarray(sample).ravel()
        rng = np.random.default_rng(self.random_state)
        average, variance = float(values.mean()), max(float(values.var()), self.min_covar)
        self.means_ = (average + rng.normal(0, math.sqrt(variance)*.05, 2))[:, None]
        self.covars_ = np.array([max(variance*.4, self.min_covar), variance*1.8])[:, None]
        self.startprob_ = np.array([.5, .5])
        self.transmat_ = np.array([[.97, .03], [.03, .97]])
        history = []
        for iteration in range(self.n_iter):
            alpha, scales, emission = self._forward(values)
            likelihood = float(np.log(scales).sum())
            history.append(likelihood)
            if len(history) >= 2 and abs(history[-1]-history[-2]) < self.tol:
                break
            backward = np.ones_like(alpha)
            for t in range(len(values)-2, -1, -1):
                backward[t] = self.transmat_@(emission[t+1]*backward[t+1])/scales[t+1]
            gamma = alpha*backward
            gamma /= gamma.sum(axis=1, keepdims=True)
            xi = (alpha[:-1, :, None]*self.transmat_[None, :, :]*
                  (emission[1:]*backward[1:])[:, None, :]/scales[1:, None, None]).sum(axis=0)
            xi = np.maximum(xi, 1e-12)
            self.transmat_ = xi/xi.sum(axis=1, keepdims=True)
            self.startprob_ = np.maximum(gamma[0], 1e-12)
            self.startprob_ /= self.startprob_.sum()
            weight = gamma.sum(axis=0)
            mean = (gamma*values[:, None]).sum(axis=0)/weight
            variance = (gamma*(values[:, None]-mean)**2).sum(axis=0)/weight
            self.means_ = mean[:, None]
            self.covars_ = np.maximum(variance, self.min_covar)[:, None]
        self.monitor_ = SimpleNamespace(history=history, iter=iteration+1)
        return self

    def score(self, sample):
        _, scales, _ = self._forward(np.asarray(sample).ravel())
        return float(np.log(scales).sum())


def ar1(p, t, h):
    r = np.diff(np.log(p[max(0, t-757):t+1]))
    design = np.column_stack([np.ones(len(r)-1), r[:-1]])
    alpha, phi = np.linalg.lstsq(design, r[1:], rcond=None)[0]
    value, total = r[-1], 0.
    for _ in range(h):
        value = alpha+phi*value
        total += value
    return float(total), float(phi)


def stats(values):
    r = np.asarray(values)
    nav = np.cumprod(1+r)
    sd = float(np.std(r, ddof=1))
    return dict(cagr=float(nav[-1]**(252/len(r))-1), volatility=float(sd*math.sqrt(252)),
                max_drawdown=float(np.min(nav/np.maximum.accumulate(np.r_[1, nav])[1:]-1)),
                sharpe_zero_cash=float(np.mean(r)/sd*math.sqrt(252)) if sd else None)


def timing(dates, p, cost):
    target = {t+1: float(p[t-19:t+1].mean() > p[t-49:t+1].mean()) for t in range(200, len(p)-1)}
    strategies = {}
    for bps in (0, cost, 2*cost):
        w, turnover, values, records = 0., 0., [], []
        for t in range(201, len(p)):
            ret = p[t]/p[t-1]-1
            growth = 1+w*ret
            w = w*(1+ret)/growth
            desired = target.get(t, w)
            trade = abs(desired-w)
            net = growth*(1-trade*bps/10000)-1
            w = desired
            turnover += trade
            values.append(net)
            records.append(dict(date=dates[t], return_=float(net), weight_after_close=w,
                                signal_information_through=dates[t-1]))
            records[-1]['return'] = records[-1].pop('return_')
        strategies[str(bps)] = dict(stats=stats(values), turnover=turnover, records=records)
    return dict(strategies=strategies, buy_hold_same_dates=stats(p[201:]/p[200:-1]-1),
                protocol='Fixed MA20>MA50 long/cash signal after t close; execute at t+1 close, earn subsequent return. Daily weight changes charge traded notional at0/base/doublebps. Cash earns zero; indices are synthetic exposures. No leverage or parameter optimization.')


def fit_gbm(p, origins, x, t, horizon):
    eligible = origins + horizon <= t
    train = origins[eligible]
    fitted = gbm().fit(x[eligible], np.log(p[train+horizon] / p[train]))
    return fitted, dict(fit_index=t, training_labels=len(train), last_training_target_index=int(train[-1]+horizon))


def forecast_scores(records):
    if not records:
        return {m: dict(rmse=None, mae=None, direction_accuracy=None, rmse_improvement_vs_mean=None,
                        rmse_improvement_vs_zero=None, coverage90=None, interval_observations=0) for m in MODELS}
    a = np.array([row['actual'] for row in records])
    means = np.array([row['predictions']['mean'] for row in records])
    mean_rmse = float(np.sqrt(np.mean((a-means)**2)))
    zero_rmse = float(np.sqrt(np.mean(a*a)))
    out = {}
    for m in MODELS:
        pred = np.array([row['predictions'][m] for row in records])
        errors = a-pred
        rmse = float(np.sqrt(np.mean(errors*errors)))
        covered = [row['intervals90'][m][0] <= row['actual'] <= row['intervals90'][m][1]
                   for row in records if row['intervals90'][m] is not None]
        out[m] = dict(rmse=rmse, mae=float(np.abs(errors).mean()),
                      direction_accuracy=float(np.mean((a > 0) == (pred > 0))),
                      rmse_improvement_vs_mean=1-rmse/mean_rmse if mean_rmse else None,
                      rmse_improvement_vs_zero=1-rmse/zero_rmse if zero_rmse else None,
                      coverage90=float(np.mean(covered)) if covered else None,
                      interval_observations=len(covered))
    return out


def purged_conformal(p, origins, x, t, h, minimum):
    calibration = np.arange(t-20*h, t, h)
    proper = origins[origins+h < calibration[0]]
    if len(proper) < minimum or calibration[0] < FEATURE_START:
        return None
    fitted = gbm().fit(x[proper-FEATURE_START], np.log(p[proper+h]/p[proper]))
    residual = np.abs(np.log(p[calibration+h]/p[calibration]) - fitted.predict(x[calibration-FEATURE_START]))
    # The finite-sample split-conformal 90% rank for 20 calibration labels is 19.
    rank = min(math.ceil((len(residual)+1)*.9), len(residual))
    q = float(np.sort(residual)[rank-1])
    prediction = float(fitted.predict(x[t-FEATURE_START:t-FEATURE_START+1])[0])
    return dict(prediction=prediction, low=prediction-q, high=prediction+q,
                calibration_observations=len(calibration), calibration_origins=calibration.tolist(),
                proper_training_labels=len(proper), last_proper_target_index=int(proper[-1]+h),
                first_calibration_index=int(calibration[0]), last_calibration_target_index=int(calibration[-1]+h))


def forecasts(dates, p, config):
    origins, x = features(p)
    out = []
    for h in config['horizons']:
        first = FEATURE_START + config['minimum_training_labels'] - 1 + h
        records, conf, errors = [], [], {m: [] for m in MODELS}
        fitted, fit_index, gbm_audit = None, -10000, None
        for t in range(first, len(p)-h, h):
            pred, audit = predict_at(p, origins, x, t, h, config)
            if fitted is None or t-fit_index >= 63:
                fitted, gbm_audit = fit_gbm(p, origins, x, t, h)
                fit_index = t
            pred['gbm'] = float(fitted.predict(x[t-FEATURE_START:t-FEATURE_START+1])[0])
            pred['ar1'], phi = ar1(p, t, h)
            actual = float(math.log(p[t+h]/p[t]))
            intervals = {m: (np.quantile(errors[m], [.05, .95])+pred[m]).tolist()
                         if len(errors[m]) >= 30 else None for m in MODELS}
            row = dict(origin=dates[t], target=dates[t+h], origin_index=t, actual=actual,
                       predictions=pred, intervals90=intervals, calibration_observations=len(errors['mean']),
                       last_training_target=dates[audit['last_training_target_index']],
                       training_labels=audit['training_labels'], gbm_audit=gbm_audit.copy(), ar1_phi=phi)
            records.append(row)
            cp = purged_conformal(p, origins, x, t, h, config['minimum_training_labels'])
            if cp is not None:
                conf.append(dict(origin=dates[t], actual=actual, mean_prediction=pred['mean'], **cp))
            for m in MODELS:
                errors[m].append(actual-pred[m])
        t = len(p)-1
        current, audit = predict_at(p, origins, x, t, h, config)
        fitted, gbm_audit = fit_gbm(p, origins, x, t, h)
        current.update(gbm=float(fitted.predict(x[-1:])[0]), ar1=ar1(p, t, h)[0])
        intervals = {m: (np.quantile(errors[m], [.05, .95])+current[m]).tolist()
                     if len(errors[m]) >= 30 else None for m in MODELS}
        cp = purged_conformal(p, origins, x, t, h, config['minimum_training_labels'])
        coverage = float(np.mean([c['low'] <= c['actual'] <= c['high'] for c in conf])) if conf else None
        out.append(dict(horizon=h, observations=len(records), scores=forecast_scores(records), records=records,
                        always_up_accuracy=float(np.mean([r['actual'] > 0 for r in records])) if records else None,
                        current=dict(origin=dates[-1], predictions=current, intervals90=intervals,
                                     training_labels=audit['training_labels'],
                                     last_training_target=dates[audit['last_training_target_index']],
                                     calibration_observations=len(records), gbm_audit=gbm_audit),
                        conformal=dict(records=conf, coverage90=coverage, observations=len(conf), current=cp,
                                       rmse=float(np.sqrt(np.mean([(c['actual']-c['prediction'])**2 for c in conf]))) if conf else None,
                                       mean_rmse_same_origins=float(np.sqrt(np.mean([(c['actual']-c['mean_prediction'])**2 for c in conf]))) if conf else None),
                        interval_protocol='Empirical prior signed forecast errors, min 30 matured nonoverlapping evaluation origins. No guaranteed coverage. Separate purged split-conformal GBM uses 20 chronological calibration origins; dependent market returns do not ensure nominal coverage.',
                        protocol='Expanding causal labels; 200-session feature warmup. GBM: interpreted histogram gradient boosted stumps,80 rounds,learningrate0.05,32 bins,minleaf40,L2=10; refit at chronological origins at least63 sessions apart. This is an explicit shallow-tree adaptation of the repository GBM family. AR1 fitted to at most756 recent returns. Current fit excluded from all evaluation scores.'))
    return out


def historical_risk(dates, p, window):
    returns = p[1:]/p[:-1]-1
    current, evaluation = {}, {}
    for c in (.95, .99):
        losses = -returns[-window:]
        var = float(np.quantile(losses, c))
        tail = losses[losses >= var]
        current[str(c)] = dict(var=var, es=float(tail.mean()), tail_count=len(tail), window=len(losses))
        records = []
        for t in range(window, len(returns)):
            threshold = float(np.quantile(-returns[t-window:t], c))
            records.append(dict(date=dates[t+1], information_through=dates[t], var=threshold,
                                breach=bool(-returns[t] > threshold)))
        hits, n = sum(r['breach'] for r in records), len(records)
        evaluation[str(c)] = dict(observations=n, breaches=hits, rate=hits/n if n else None,
                                  expected_rate=1-c, binomial_p_value=float(binomtest(hits, n, 1-c).pvalue) if n else None,
                                  records=records)
    return dict(current=current, evaluation=evaluation,
                note='One-session historical VaR / expected shortfall. Causal rolling evaluation. Binomial exception test assumes independent breaches; this is not a risk certification.')


def har(dates, raw, minimum):
    o, h, l, c = [np.array([float(row[k]) for row in raw]) for k in ('open', 'high', 'low', 'close')]
    v = np.sqrt(np.maximum(.5*np.log(h/l)**2-(2*np.log(2)-1)*np.log(c/o)**2, 0)*252)
    x = np.array([[1, v[t-1], v[t-5:t].mean(), v[t-22:t].mean()] for t in range(22, len(v))])
    ew = float(np.mean(v[:60]**2))
    coef, records = None, []
    first = 22+minimum
    for t in range(60, len(v)):
        if t >= first:
            if (t-first) % 63 == 0:
                coef = np.linalg.lstsq(x[:t-22], v[22:t], rcond=None)[0]
                fitted_through = dates[t-1]
            records.append(dict(date=dates[t], information_through=dates[t-1], parameter_fit_through=fitted_through,
                                har=max(float(x[t-22]@coef), .0001), ewma_gk=math.sqrt(ew),
                                rolling22_gk=math.sqrt(float(np.mean(v[t-22:t]**2))), actual=float(v[t])))
        ew = .94*ew+.06*v[t]**2
    scores = {}
    a = np.array([row['actual'] for row in records])
    for name in ('har', 'ewma_gk', 'rolling22_gk'):
        pred = np.array([row[name] for row in records])
        variance = np.maximum(pred**2/252, 1e-12)
        scores[name] = dict(volatility_rmse=float(np.sqrt(np.mean((a-pred)**2))) if len(a) else None,
                            qlike=float(np.mean(np.log(variance)+(a*a/252)/variance)) if len(a) else None)
    coef = np.linalg.lstsq(x, v[22:], rcond=None)[0]
    query = np.array([1, v[-1], v[-5:].mean(), v[-22:].mean()])
    return dict(scores=scores, records=records, observations=len(records), current=max(float(query@coef), .0001),
                coefficients=coef.tolist(), minimum_training_labels=minimum,
                proxy='Daily OHLC Garman–Klass annualized volatility, not intraday realized volatility. HAR, EWMA and rolling scores use the same proxy, separately from close-return GARCH. Unadjusted same-day OHLC ratios; no price-level return is substituted.')


def regime(dates, p, window):
    r = np.diff(np.log(p))*100
    rows, diagnostics = [], []
    fitted = None
    for t in range(window, len(r)):
        if (t-window) % 126 == 0:
            sample = r[t-window:t, None]
            candidates = []
            for seed in (7, 29):
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    m = GaussianHMM(n_components=2, covariance_type='diag', n_iter=100, tol=.001,
                                    random_state=seed, min_covar=.001).fit(sample)
                candidates.append(m)
            fitted = max(candidates, key=lambda m: m.score(sample))
            mean = fitted.means_.ravel()
            variance = fitted.covars_.reshape(2, -1)[:, 0]
            stress = int(np.argmax(variance))
            prob = fitted.startprob_.copy()
            for j, value in enumerate(sample[:, 0]):
                log_weight = norm.logpdf(value, mean, np.sqrt(variance))
                prior = prob if j == 0 else prob @ fitted.transmat_
                prob = prior*np.exp(log_weight-log_weight.max())
                prob /= prob.sum()
            fit_through = dates[t]
            history = list(fitted.monitor_.history)
            diagnostics.append(dict(parameter_fit_through=fit_through, training_returns=window,
                                    iterations=int(fitted.monitor_.iter),
                                    converged=bool(len(history) >= 2 and abs(history[-1]-history[-2]) < fitted.tol),
                                    final_log_likelihood_change=float(history[-1]-history[-2]) if len(history) >= 2 else None))
        log_weight = norm.logpdf(r[t], mean, np.sqrt(variance))
        prob = (prob @ fitted.transmat_)*np.exp(log_weight-log_weight.max())
        prob /= prob.sum()
        rows.append(dict(date=dates[t+1], stress_probability=float(prob[stress]),
                         parameter_fit_through=fit_through, stress_annual_vol=float(math.sqrt(variance[stress]*252)/100)))
    return dict(records=rows, current=rows[-1], observations=len(rows), transition_matrix=fitted.transmat_.tolist(),
                state_daily_mean_percent=mean.tolist(), state_daily_variance_percent_squared=variance.tolist(),
                converged=diagnostics[-1]['converged'], refits=diagnostics, training_window=window,
                protocol='Two Gaussian return states fitted by interpreted NumPy/SciPy scaled forward/backward EM on historical training data only, two fixed initialization seeds, rolling window, refit every126 sessions. Evaluation probabilities use normalized forward filtering only; no future smoothing. Parameters known before that session return; stress labels identify higher fitted variance, not recessions.')


def beta_for_asset(meta, dates, p, spy):
    if meta['id'] == 'ihsg':
        return dict(available=False, benchmark='SPY', reason='IDR index returns cannot be compared with USD benchmark returns without a matched currency conversion series.')
    sd, sp, _ = spy
    lookup = dict(zip(sd, sp))
    aligned = [(d, v, lookup[d]) for d, v in zip(dates, p) if d in lookup]
    d = [row[0] for row in aligned]
    asset = np.array([row[1] for row in aligned])
    benchmark = np.array([row[2] for row in aligned])
    beta = kalman_beta(asset, benchmark, d)
    beta.update(available=True, benchmark='SPY adjusted-close return proxy', matched_prices=len(d),
                first=d[0], last=d[-1], currency='USD')
    return beta


def fit_asset(meta, spy_meta):
    with threadpool_limits(limits=1):
        d, p, raw = load_series(meta)
        # A predeclared short-history protocol, not a fitted-performance selection.
        minimum = 252 if len(p) < 1200 else 756
        cfg = {**CONFIG, 'minimum_training_labels': minimum}
        risk_window = 252 if len(p)-1 < 1008 else 756
        print(f"{meta['id']}: {len(p)} prices, {minimum} matured training labels; fitting quant families", flush=True)
        f = forecasts(d, p, cfg)
        vol = volatility(d, p, cfg)
        vol['observations'] = len(vol['records'])
        vol['minimum_training_returns'] = minimum
        vol['protocol'] = 'Gaussian quasi-likelihood GARCH(1,1), expanding training, stationarity constraint alpha+beta<=0.999, refit every 63 sessions; EWMA lambda0.94 and rolling60 share causal close-return squared-realization evaluation. Current all-data fit excluded from test scores.'
        risk = historical_risk(d, p, risk_window)
        scen = scenarios(p, cfg)
        visual = visual_scenarios({meta['id']: (d, p)}, cfg, {})[meta['id']]
        raw_close = float(raw[-1]['close'])
        multiplier = raw_close/p[-1]
        for bands in scen['bands'].values():
            for row in bands:
                for key in ('p05', 'p50', 'p95'):
                    row[key] *= multiplier
        scen.update(price_anchor=raw_close, currency=meta['currency'],
                    note='Conditional 5/20-session simulations from observed return history, anchored to latest raw quote. Pointwise bands are not validated forecast intervals, option-market probabilities or 5–10-year investment forecasts.')
        summary = descriptive(d, p)
        summary['trend'] = 'Above MA200' if p[-1] >= summary['ma200'] else 'Below MA200'
        summary['volatility_regime'] = 'High' if summary['vol20'] > summary['volatility_p90_past'] else 'Normal'
        for row, original in zip(summary['history'], raw):
            row.update(raw_close=float(original['close']), volume=float(original['volume']) if original['volume'] else None)
        returns = np.diff(np.log(p))
        _, x = features(p)
        momentum = {str(h): float(p[-1]/p[-1-h]-1) for h in (1, 5, 20, 60, 252)}
        result = dict(meta={k: meta[k] for k in ('id', 'symbol', 'name', 'currency', 'instrument', 'definition')},
                      cutoff=d[-1], latest_unadjusted_close=raw_close, summary=summary, forecasts=f,
                      volatility=vol, risk=risk, scenarios=scen, visual_scenarios=visual,
                      har=har(d, raw, minimum), regime=regime(d, p, minimum),
                      timing=timing(d, p, 30 if meta['id'] == 'ihsg' else 10),
                      distribution=dict(skew=float(skew(returns)), excess_kurtosis=float(kurtosis(returns)),
                                        acf1=float(np.corrcoef(returns[1:], returns[:-1])[0, 1]),
                                        worst_daily_log_return=float(returns.min()), best_daily_log_return=float(returns.max()),
                                        momentum=momentum),
                      technical=dict(rsi14=float(x[-1, 8]*100), distance_ma50=float(x[-1, 6]),
                                     distance_ma200=float(x[-1, 7]), momentum=momentum),
                      beta=beta_for_asset(meta, d, p, load_series(spy_meta)),
                      config=cfg, model_implementations=IMPLEMENTATIONS,
                      data=dict(first=d[0], cutoff=d[-1], rows=len(p), price_field=meta['price_field'],
                                minimum_training_labels=minimum, risk_window=risk_window,
                                source_sha256=meta['csv_sha256'], csv_file=meta['csv_file'], raw_file=meta['raw_file'],
                                short_history=minimum == 252),
                      limitations=['Retrospectively selected tickers; no point-in-time constituent universe.',
                                   'Historical adjusted prices reflect the current provider revision, not original historical data vintages.',
                                   'Models forecast 5 and 20 trading sessions; no validated 5–10-year price target or buy/sell rating.',
                                   'Short-history protocol reduces fixed training thresholds to 252 labels when fewer than1200 prices exist; model scores then have fewer independent test origins.'] if minimum == 252 else
                                  ['Retrospectively selected tickers; no point-in-time constituent universe.',
                                   'Historical adjusted prices reflect the current provider revision, not original historical data vintages.',
                                   'Models forecast 5 and 20 trading sessions; no validated 5–10-year price target or buy/sell rating.'])
        json.dumps(result, allow_nan=False)
        (DATA / (meta['id'] + '-models.json')).write_text(json.dumps(result, allow_nan=False, separators=(',', ':')), encoding='utf-8')
        print(f"{meta['id']}: complete; forecast test origins {[(z['horizon'], z['observations']) for z in f]}", flush=True)
        return meta['id'], result


def factors(datasets, include_benchmark=False):
    url = 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip'
    path = DATA / 'ff5-monthly-raw.zip'
    if not path.exists():
        path.write_bytes(fetch(url))
    with zipfile.ZipFile(path) as archive:
        text = archive.read(archive.namelist()[0]).decode('utf-8-sig')
    ff = {}
    for line in text.splitlines():
        cells = line.strip().split(',')
        if len(cells) >= 7 and re.fullmatch(r'\d{6}', cells[0].strip()):
            ff[cells[0].strip()] = np.array([float(v)/100 for v in cells[1:7]])
    assets = {}
    for meta in datasets:
        if meta['id'] == 'ihsg' or (meta['id'] == 'spy' and not include_benchmark):
            continue
        dates, p, _ = load_series(meta)
        last = {}
        for date, price in zip(dates, p):
            last[date[:7].replace('-', '')] = price
        months = sorted(last)
        rows = [(month, last[month]/last[previous]-1, ff[month])
                for previous, month in zip(months, months[1:]) if month in ff and month <= '202608']
        result = {}
        for name, k in [('capm', 1), ('ff3', 3), ('ff5', 5)]:
            if len(rows) < max(12, k+7):
                result[name] = dict(available=False, months=len(rows), reason='Insufficient completed matched monthly factors.')
                continue
            x = np.column_stack([np.ones(len(rows)), np.array([row[2][:k] for row in rows])])
            y = np.array([row[1]-row[2][5] for row in rows])
            b = np.linalg.lstsq(x, y, rcond=None)[0]
            residual = y-x@b
            u = x*residual[:, None]
            meat = u.T@u
            for lag in range(1, 4):
                g = u[lag:].T@u[:-lag]
                meat += (1-lag/4)*(g+g.T)
            bread = np.linalg.pinv(x.T@x)
            se = np.sqrt(np.maximum(np.diag(bread@meat@bread)*len(rows)/(len(rows)-x.shape[1]), 0))
            tss = float((y-y.mean())@(y-y.mean()))
            result[name] = dict(available=True, months=len(rows), start=rows[0][0], end=rows[-1][0],
                                monthly_alpha=float(b[0]), annualized_alpha_linear=float(b[0]*12),
                                alpha_hac_t=float(b[0]/se[0]) if se[0] else None,
                                coefficients=b.tolist(), hac_standard_errors=se.tolist(),
                                r_squared=1-float(residual@residual)/tss if tss else None,
                                residual_degrees_of_freedom=len(rows)-x.shape[1])
        assets[meta['id']] = result
    assets['ihsg'] = dict(available=False, reason='IDR index lacks matched local risk-free rate and currency-adjusted US factor returns.')
    return dict(assets=assets, labels=['Intercept', 'Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA'],
                source=dict(url=url, file=relative(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()),
                protocol='Completed matched calendar months through August2026, never September before factor publication. Actual US RF subtracted; three-lag HAC standard errors. Current Kenneth French file revision, descriptive full-sample attribution. Alpha is not evidence of a tradable edge. Index price returns exclude dividends whereas US factors include them.')


def portfolio_styles(datasets, ids=None, presets=None):
    ids = ids or ['tsm', 'nvda', 'avgo', 'mu', 'etn', 'vrt', 'alab', 'crdo']
    lookup = {item['id']: item for item in datasets}
    series = {id: load_series(lookup[id]) for id in ids}
    common = sorted(set.intersection(*(set(value[0]) for value in series.values())))
    dates = common[-253:]
    prices = np.column_stack([[dict(zip(series[id][0], series[id][1]))[date] for date in dates] for id in ids])
    returns = prices[1:]/prices[:-1]-1
    covariance = np.cov(returns, rowvar=False)
    shrunk = .9*covariance+.1*np.diag(np.diag(covariance))
    sd = np.sqrt(np.diag(covariance))
    correlation = covariance/np.outer(sd, sd)
    presets = presets or {'aggressive': [20, 15, 15, 10, 15, 10, 7.5, 7.5],
               'infrastructure': [15, 10, 10, 5, 25, 20, 7.5, 7.5],
               'core': [25, 15, 20, 5, 20, 15, 0, 0]}
    styles = {}
    for name, weight in presets.items():
        w = np.array(weight)/100
        variance = float(w@shrunk@w)
        records, values, nav, turnover = [], [], 1., 0.
        for i, r in enumerate(returns):
            growth = float(1+w@r)
            drift = w*(1+r)/growth
            trade = float(np.abs(w-drift).sum())
            entry = 1. if i == 0 else 0.
            net = growth*(1-entry*.001)*(1-trade*.001)-1
            nav *= 1+net
            values.append(net)
            turnover += trade+entry
            records.append(dict(date=dates[i+1], nav=float(nav), return_=float(net),
                                traded_notional=float(trade+entry)))
            records[-1]['return'] = records[-1].pop('return_')
        risk = {}
        for c in (.95, .99):
            losses = -np.array(values)
            var = float(np.quantile(losses, c))
            tail = losses[losses >= var]
            risk[str(c)] = dict(var=var, es=float(tail.mean()), tail_count=len(tail), window=len(values))
        styles[name] = dict(weights={id: float(v) for id, v in zip(ids, w)},
                            annual_volatility=float(math.sqrt(variance*252)),
                            risk_contributions={id: float(v) for id, v in zip(ids, w*(shrunk@w)/variance)},
                            historical=stats(values), records=records, historical_risk=risk,
                            turnover=turnover, cost_bps_per_traded_notional=10)
    return dict(ids=ids, observations=len(returns), first=dates[1], last=dates[-1],
                correlation=correlation.tolist(), covariance_daily=shrunk.tolist(), styles=styles,
                protocol='USD adjusted-close proxies on253 shared prices /252 returns; sample covariance with fixed10% diagonal shrinkage. Fixed current style weights replayed retrospectively, daily constant-weight rebalancing,10bps per traded notional including entry, zero-return cash. Not an optimized portfolio or point-in-time strategy backtest. Risk contributions are fractional variance contributions, not weights. Historical VaR/ES uses one-session net simple returns. FX, taxes, spreads and real execution restrictions are excluded.')


def validate(result):
    assert set(result['assets']) == {a['id'] for a in ASSETS}
    for id, a in result['assets'].items():
        assert a['data']['cutoff'] == CUTOFF
        assert a['latest_unadjusted_close'] > 0 and a['summary']['close'] > 0
        for f in a['forecasts']:
            assert f['observations'] == len(f['records']) > 0
            assert f['current']['last_training_target'] <= CUTOFF
            assert set(f['current']['predictions']) == set(MODELS)
            for i, row in enumerate(f['records']):
                assert row['last_training_target'] <= row['origin'] < row['target'] <= CUTOFF
                assert row['gbm_audit']['last_training_target_index'] <= row['gbm_audit']['fit_index'] <= row['origin_index']
                assert row['calibration_observations'] == i
                assert all((row['intervals90'][m] is None) == (i < 30) for m in MODELS)
            assert all((f['current']['intervals90'][m] is None) == (f['observations'] < 30) for m in MODELS)
            for row in f['conformal']['records'] + ([f['conformal']['current']] if f['conformal']['current'] else []):
                assert row['last_proper_target_index'] < row['first_calibration_index']
                assert row['last_calibration_target_index'] <= len(a['summary']['history'])-1
        for row in a['volatility']['records']:
            assert row['information_through'] < row['date']
            assert all(row[m] > 0 for m in ('garch', 'ewma', 'rolling60'))
        for models in a['visual_scenarios']['models'].values():
            assert len(models['sample_paths']) == 60
            assert all(sum(hist['counts']) == 5000 for hist in models['histograms'].values())
        assert all(0 <= row['stress_probability'] <= 1 for row in a['regime']['records'])
    json.dumps(result, allow_nan=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3, help='Independent fitting processes; each limits numerical threads to one.')
    parser.add_argument('--reuse-models', action='store_true', help='Reuse completed new-snapshot model artifacts after interrupted work.')
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    captured = dt.datetime.now(dt.timezone.utc).isoformat()
    print('Acquiring retained daily sources through ' + CUTOFF, flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        datasets = list(executor.map(acquire, [*ASSETS, BENCHMARK]))
    provenance = dict(requested_start=START, requested_end=CUTOFF, acquired_utc=captured,
                      datasets=datasets, errors=[], snapshot_definition='Completed regular exchange sessions through September30,2026. Live intraday quote refreshes do not refit these models.')
    (DATA / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    print('Sources: ' + ', '.join(f"{m['id']}={m['rows']}" for m in datasets), flush=True)
    spy = next(m for m in datasets if m['id'] == 'spy')
    assets, pending = {}, []
    for meta in datasets:
        if meta['id'] == 'spy':
            continue
        path = DATA / (meta['id'] + '-models.json')
        if args.reuse_models and path.exists():
            assets[meta['id']] = read_json(path)
            assets[meta['id']]['model_implementations'] = IMPLEMENTATIONS
            for row in assets[meta['id']]['forecasts']:
                row['protocol'] = 'Expanding causal labels;200-session warmup. Interpreted histogram gradient boosted stumps:80 rounds,learningrate0.05,32 bins,minleaf40,L2=10; refit at chronological origins at least63 sessions apart. Explicit shallow-tree repository adaptation. AR1 uses at most756 recent returns. Current fit is excluded from evaluation scores.'
            assets[meta['id']]['regime']['protocol'] = 'Two Gaussian return states fitted by interpreted NumPy/SciPy scaled EM on historical training data only. Two fixed seeds, rolling window,126-session refit. Evaluation probabilities are forward filtered only, with parameters known before that session return; no future smoothing.'
        else:
            pending.append(meta)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(fit_asset, meta, spy) for meta in pending]
        for future in concurrent.futures.as_completed(futures):
            id, model = future.result()
            assets[id] = model
    attribution = factors(datasets)
    for id, model in assets.items():
        model['factors'] = attribution['assets'].get(id, dict(available=False, reason='No matched completed monthly factors.'))
        if id == 'vrt':
            caveat = 'The linked VRT provider price history before 10 February 2020 includes the predecessor/SPAC phase; it is not a continuous history of the current Vertiv operating business.'
            if caveat not in model['limitations']:
                model['limitations'].append(caveat)
            model['data']['history_context_source'] = 'https://investors.vertiv.com/financials/annual-reports/2021-Shareholder-Letter/'
    reviewed = read_json(ROOT / 'repo-review' / 'reviewed.json')
    source_hashes = {relative(path): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in [Path(__file__), ROOT / 'models.py', ROOT / 'visual_scenarios.py', ROOT.parent / 'output' / 'garch_nvda.py']}
    for path in [ROOT / 'repo-review' / 'reviewed.json', *[ROOT / item['text_file'] for item in reviewed]]:
        source_hashes[relative(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = dict(schema_version=1, cutoff=CUTOFF, generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  config=CONFIG, assets={a['id']: assets[a['id']] for a in ASSETS},
                  factors=attribution, portfolios=portfolio_styles(datasets), provenance=provenance,
                  model_families=['Ridge', 'OLS', 'KNN50', 'GBM', 'AR1', 'Mean and zero baselines',
                                  'Purged split-conformal GBM', 'GARCH(1,1)', 'EWMA', 'Rolling volatility',
                                  'HAR Garman–Klass proxy', 'Forward Gaussian HMM', 'Historical VaR/ES',
                                  'Block-bootstrap and zero-log-drift GBM simulation', 'Kalman SPY beta',
                                  'CAPM / Fama–French3 / Fama–French5 with HAC', 'Delayed MA20/MA50 timing'],
                  repository_methods=dict(core='market_models/models.py', additions='market_models/research_upgrade.py',
                                          reviewed='market_models/repo-review/reviewed.json',
                                          legacy_snapshots_preserved=True),
                  repository_sources=reviewed, source_hashes=source_hashes,
                  model_implementations=IMPLEMENTATIONS,
                  repository_method_mapping={'ridge_ols_knn': '11_ml_pipeline/02_regularization_paths.py + existing models.py causal features',
                                             'gbm': '12_gradient_boosting/02_gbm_comparison.py; explicit interpreted histogram-stump adaptation',
                                             'conformal': '12_gradient_boosting/11_conformal_gbm.py; purged proper training and20 chronological calibration labels',
                                             'ar1': '09_model_based_features/07_arima_features.py; fixed AR1 adaptation',
                                             'garch': '09_model_based_features volatility notebooks; existing audited output/garch_nvda.py',
                                             'har': '09_model_based_features/09_har_rough_volatility.py; OHLC Garman–Klass proxy adaptation',
                                             'regime': '09_model_based_features/11_hmm_regimes.py; interpreted two-state EM and forward evaluation',
                                             'risk': '19_risk_management/01_var_cvar.py; causal rolling historical VaR/ES',
                                             'beta': 'Financial-Models-Numerical-Methods Kalman notebooks; existing audited models.py filter',
                                             'factors': '19_risk_management/04_factor_exposure.py; actual completed Kenneth French monthly factors and HAC',
                                             'timing': '16_strategy_simulation/01_backtest_first_principles.py; delayed execution and costs',
                                             'portfolio_risk': '17_portfolio_construction/01_portfolio_metrics.py; fixed style covariance/risk attribution, not optimized weights'},
                  protocol='13 actual fitted assets, isolated fresh snapshot. Stocks use Yahoo adjusted-close return proxies; three indices use price-index closes. Public raw quotes, historical adjusted model inputs and scenario USD anchors are explicitly separate. All evaluation uses chronological information sets and matured targets. Seven competing return models, baseline comparisons and realized interval coverage are retained; a model fit does not imply predictive outperformance. Training threshold252 applies only to histories shorter than1200 prices; otherwise756. Prices and models cover September30,2026 completed sessions; factor attribution ends August2026. No validated5–10-year forecasts or fundamental intrinsic valuation in these statistical models.')
    validate(result)
    RESULT.write_text(json.dumps(result, allow_nan=False, separators=(',', ':')), encoding='utf-8')
    print('Saved ' + relative(RESULT) + ' (' + str(RESULT.stat().st_size) + ' bytes)', flush=True)
    for id, model in result['assets'].items():
        print(id, model['data']['rows'], [(f['horizon'], f['observations'], f['current']['calibration_observations']) for f in model['forecasts']], flush=True)


if __name__ == '__main__':
    main()
