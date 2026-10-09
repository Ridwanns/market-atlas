"""User-selected four-asset dashboard extension; original research stays frozen.

Run before rebuilding the shell. SPY receives actual repository quant fits from
the same retained September 30 adjusted-price source, never copied index scores.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import ai_quant as quant

ROOT=Path(__file__).resolve().parent
FOCUS_IDS=['nvda','tsm','mu','spy']
WEIGHTS={'nvda':.40,'tsm':.25,'mu':.20,'spy':.15}
PATH=ROOT/'results/2026-10-09/focused-portfolio.json'

def main():
    original=ROOT/'results/2026-09-30/quant-refresh.json'
    q=json.loads(original.read_text(encoding='utf-8'))
    datasets=q['provenance']['datasets']
    spy=next(row for row in datasets if row['id']=='spy')
    spy=dict(spy,instrument='US-listed S&P 500 ETF')
    cache=quant.DATA/'spy-models.json'
    if cache.exists():
        fitted=json.loads(cache.read_text(encoding='utf-8'))
    else:
        _,fitted=quant.fit_asset(spy,spy)
    fitted['factors']=quant.factors([spy],include_benchmark=True)['assets']['spy']
    q['factors']['assets']['spy']=fitted['factors']
    q['assets']['spy']=fitted
    q['assets']={i:q['assets'][i] for i in FOCUS_IDS+['sp500','nasdaq','ihsg']}
    q['portfolios']=quant.portfolio_styles(datasets,ids=FOCUS_IDS,
        presets={'focus':[40,25,20,15]})
    q['focus']={'ids':FOCUS_IDS,'weights':WEIGHTS,'updated':'2026-10-09',
        'definition':'User-selected targets for the equity portfolio, not verified actual positions or optimized weights.',
        'original_report_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
        'model_cutoff':q['cutoff'],'spy_source_sha256':spy['csv_sha256'],
        'generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'extension_source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__),ROOT/'ai_quant.py']}}
    q['protocol']='Focused dashboard extension: NVDA/TSM/MU/SPY plus three retained indices. SPY fitted from its own adjusted-close series under the same September 30 quant protocol. Quotes refresh separately. Original 13-asset research remains archived.'
    p=q['portfolios']; assert sum(WEIGHTS.values())==1
    assert p['ids']==FOCUS_IDS and p['styles']['focus']['weights']==WEIGHTS
    assert len(fitted['forecasts'])==2
    for f in fitted['forecasts']:
        assert f['current']['last_training_target']<=q['cutoff']
        assert all(r['last_training_target']<=r['origin']<r['target']<=q['cutoff'] for r in f['records'])
    PATH.parent.mkdir(parents=True,exist_ok=True)
    PATH.write_text(json.dumps(q,allow_nan=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'focus':WEIGHTS,'cutoff':q['cutoff'],'portfolio_vol':p['styles']['focus']['annual_volatility'],'output':str(PATH)}),flush=True)

if __name__=='__main__':main()
