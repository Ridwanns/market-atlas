"""Freeze dated predictions and score only genuinely prospective registrations.

The ledger is public research data, not a brokerage or trade history. A model
snapshot can be registered once. Late registrations never enter forward scores.
"""
import concurrent.futures
import datetime as dt
import hashlib
import json
import math
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'results/2026-09-30/quant-refresh.json'
LEDGER = ROOT / 'results/live/forecast-monitor.json'
LOCK = threading.Lock()
PROTOCOL = (
    'Frozen 5/20-session adjusted-close log-return forecasts. Registration must precede '
    'the first post-origin regular session open. Provider session timestamps determine '
    'eligibility; unknown and late registrations are excluded. Outcomes use completed '
    'daily adjusted closes in one retrieval vintage. No refitting, automatic trades, '
    'or backdated prospective results. Overlapping horizons are not independent samples.'
)


def utc(stamp):
    return dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat()


def exchange_date(stamp, offset):
    return dt.datetime.fromtimestamp(stamp + offset, dt.timezone.utc).date().isoformat()


def fetch_daily(symbol, origin_date=None):
    parameters = {'interval': '1d'}
    if origin_date:
        parameters.update(period1=int(dt.datetime.fromisoformat(origin_date).replace(tzinfo=dt.timezone.utc).timestamp()), period2=int(time.time()) + 60)
    else:
        parameters['range'] = '3mo'
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + urllib.parse.quote(symbol, safe='') + '?' + urllib.parse.urlencode(parameters)
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=18) as response:
        raw = response.read()
    parsed = json.loads(raw)
    chart = parsed['chart']['result'][0]
    captured = time.time()
    digest = hashlib.sha256(raw).hexdigest()
    directory = ROOT / 'data/forecast-monitor'
    directory.mkdir(parents=True, exist_ok=True)
    filename = symbol.replace('^', 'index-').lower() + '-' + digest[:16] + '.json'
    path = directory / filename
    if not path.exists():
        path.write_bytes(raw)
    return {'chart': chart, 'captured_utc': utc(captured), 'source': url,
            'sha256': digest, 'raw_file': str(path.relative_to(ROOT))}


def completed_bars(observation, now):
    chart = observation['chart']
    meta = chart['meta']
    offset = meta.get('gmtoffset', 0)
    local_day = exchange_date(now, offset)
    regular = meta.get('currentTradingPeriod', {}).get('regular', {})
    adj = chart.get('indicators', {}).get('adjclose') or []
    prices = adj[0].get('adjclose', []) if adj else []
    rows = []
    for stamp, price in zip(chart.get('timestamp', []), prices):
        day = exchange_date(stamp, offset)
        closed = day < local_day or (day == local_day and regular.get('end', float('inf')) <= now)
        if closed and isinstance(price, (int, float)) and math.isfinite(price) and price > 0:
            rows.append({'date': day, 'open_utc': utc(stamp), 'open_stamp': stamp, 'price': price})
    return sorted({row['date']: row for row in rows}.values(), key=lambda row: row['date'])


def eligibility(origin, observation, registered):
    """Conservative session-open check; absence of evidence does not imply eligible."""
    chart = observation['chart']
    meta = chart['meta']
    offset = meta.get('gmtoffset', 0)
    later = [stamp for stamp in chart.get('timestamp', []) if exchange_date(stamp, offset) > origin]
    if later:
        first_open = min(later)
        return ('eligible' if registered < first_open else 'late'), utc(first_open)
    regular = meta.get('currentTradingPeriod', {}).get('regular', {})
    upcoming = regular.get('start')
    if upcoming is not None and exchange_date(upcoming, offset) > origin:
        return ('eligible' if registered < upcoming else 'late'), utc(upcoming)
    return 'unknown', None


def settle(record, observation, now):
    if record['eligibility'] != 'eligible' or record['status'] == 'scored':
        return
    rows = completed_bars(observation, now)
    origin = next((row for row in rows if row['date'] == record['origin']), None)
    future = [row for row in rows if row['date'] > record['origin']]
    if not origin or len(future) < record['horizon']:
        return
    target = future[record['horizon'] - 1]
    actual = math.log(target['price'] / origin['price'])
    record.update(status='scored', target_date=target['date'], actual_log_return=actual,
                  scored_utc=utc(now), origin_adjusted_close=origin['price'],
                  target_adjusted_close=target['price'], outcome_source={
                      key: observation[key] for key in ['source', 'sha256', 'raw_file', 'captured_utc']})


def summarize(records):
    metrics = []
    groups = sorted({(row['asset'], row['horizon'], row['model']) for row in records if row['status'] == 'scored'})
    for asset, horizon, model in groups:
        scored = [row for row in records if row['status'] == 'scored' and row['asset'] == asset and row['horizon'] == horizon and row['model'] == model]
        errors = [row['prediction'] - row['actual_log_return'] for row in scored]
        matches = []
        mean_errors = []
        zero_errors = []
        for row in scored:
            key = (row['report_sha256'], row['asset'], row['horizon'], row['origin'])
            peers = {peer['model']: peer for peer in records if peer['status'] == 'scored' and
                     (peer['report_sha256'], peer['asset'], peer['horizon'], peer['origin']) == key}
            if 'mean' in peers and 'zero' in peers:
                matches.append(row['prediction'] - row['actual_log_return'])
                mean_errors.append(peers['mean']['prediction'] - row['actual_log_return'])
                zero_errors.append(peers['zero']['prediction'] - row['actual_log_return'])
        rmse = lambda values: math.sqrt(sum(value * value for value in values) / len(values)) if values else None
        intervals = [row for row in scored if isinstance(row.get('interval90_log_return'), list) and len(row['interval90_log_return']) == 2]
        coverage = sum(row['interval90_log_return'][0] <= row['actual_log_return'] <= row['interval90_log_return'][1] for row in intervals) / len(intervals) if intervals else None
        metrics.append({'asset': asset, 'horizon': horizon, 'model': model, 'observations': len(scored),
                        'rmse_log_return': rmse(errors), 'mae_log_return': sum(abs(e) for e in errors) / len(errors),
                        'coverage90': coverage, 'interval_observations': len(intervals),
                        'matched_observations': len(matches), 'matched_rmse': rmse(matches),
                        'mean_rmse_same_origins': rmse(mean_errors), 'zero_rmse_same_origins': rmse(zero_errors)})
    return {'registered_records': len(records), 'pending': sum(row['status'] == 'pending' for row in records),
            'scored': sum(row['status'] == 'scored' for row in records),
            'late': sum(row['eligibility'] == 'late' for row in records),
            'unknown': sum(row['eligibility'] == 'unknown' for row in records), 'metrics': metrics}


def update_monitor(report_path=REPORT, ledger_path=LEDGER, fetcher=fetch_daily, now=None, force=False):
    with LOCK:
        stamp = time.time() if now is None else now
        raw = report_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        report = json.loads(raw)
        ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {
            'schema_version': 1, 'registered_utc': utc(stamp), 'records': [], 'errors': [], 'protocol': PROTOCOL}
        last = ledger.get('checked_stamp', 0)
        known_report = any(row['report_sha256'] == digest for row in ledger['records'])
        if known_report and not force and stamp - last < 900:
            return ledger
        observations, errors = {}, []
        def acquire(item):
            asset, symbol = item
            try:
                needed = [forecast['current']['origin'] for forecast in report['assets'][asset]['forecasts']]
                needed += [row['origin'] for row in ledger['records'] if row['asset'] == asset and row['status'] == 'pending']
                observation = fetch_daily(symbol, min(needed)) if fetcher is fetch_daily else fetcher(symbol)
                return asset, observation, None
            except Exception as exc:
                return asset, None, {'asset': asset, 'error': str(exc)[:300], 'checked_utc': utc(stamp)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(acquire, [(asset, data['meta']['symbol']) for asset, data in report['assets'].items()]))
        # Registration time follows acquisition, so a request crossing session
        # open cannot claim it was frozen before the opening observation.
        stamp = time.time() if now is None else now
        for asset, observation, error in results:
            if error:
                errors.append(error)
            else:
                observations[asset] = observation
        existing = {row['key'] for row in ledger['records']}
        for asset, data in report['assets'].items():
            for forecast in data['forecasts']:
                current = forecast['current']
                for model, prediction in current['predictions'].items():
                    key = '|'.join(map(str, [digest, asset, forecast['horizon'], model, current['origin']]))
                    if key in existing:
                        continue
                    observation = observations.get(asset)
                    eligible, first_open = eligibility(current['origin'], observation, stamp) if observation else ('unknown', None)
                    ledger['records'].append({
                        'key': key, 'report_sha256': digest, 'asset': asset,
                        'horizon': forecast['horizon'], 'model': model, 'origin': current['origin'],
                        'registered_utc': utc(stamp), 'prediction': prediction,
                        'interval90_log_return': current['intervals90'].get(model),
                        'last_training_target': current['last_training_target'],
                        'input_sha256': data['data']['source_sha256'],
                        'eligibility': eligible, 'first_post_origin_open_utc': first_open,
                        'registration_source': {key: observation[key] for key in ['source', 'sha256', 'raw_file', 'captured_utc']} if observation else None,
                        'status': 'pending' if eligible == 'eligible' else 'excluded',
                        'target_date': None, 'actual_log_return': None})
        for record in ledger['records']:
            if record['asset'] in observations:
                settle(record, observations[record['asset']], stamp)
        ledger.update(checked_utc=utc(stamp), checked_stamp=stamp, errors=errors,
                      summary=summarize(ledger['records']), protocol=PROTOCOL)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temp = ledger_path.with_suffix('.tmp')
        temp.write_text(json.dumps(ledger, indent=2, allow_nan=False), encoding='utf-8')
        temp.replace(ledger_path)
        return ledger


if __name__ == '__main__':
    print(json.dumps(update_monitor()['summary'], indent=2))
