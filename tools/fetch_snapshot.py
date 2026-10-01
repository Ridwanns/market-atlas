"""Public market snapshots; no broker credentials or fabricated fallback prices."""
import concurrent.futures
import datetime as dt
import gzip
import json
import shutil
from pathlib import Path
from live_server import fetch_quote, SYMBOLS
from forecast_monitor import update_monitor

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'site/data'
DATA.mkdir(parents=True, exist_ok=True)
previous_path = DATA / 'quotes.json'
previous = json.loads(previous_path.read_text()) if previous_path.exists() else {'quotes': []}
old = {quote['symbol']: quote for quote in previous['quotes']}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    rows = list(pool.map(fetch_quote, SYMBOLS))
valid = [row for row in rows if 'error' not in row]
failures = [row for row in rows if 'error' in row]
if not valid and not old:
    raise RuntimeError('No public quotes retrieved; an initial snapshot cannot be fabricated')
# Partial failures retain the original observation time and disclose the error.
for index, row in enumerate(rows):
    if 'error' in row and row['symbol'] in old:
        rows[index] = dict(old[row['symbol']], refresh_error=row['error'])
now = dt.datetime.now(dt.timezone.utc)
payload = {'fetched_utc': now.isoformat(), 'fetched_wib': now.astimezone(dt.timezone(dt.timedelta(hours=7))).isoformat(),
    'quotes': rows, 'publish_mode': 'github-pages-snapshot', 'refresh_seconds': 7200,
    'provider': 'Yahoo Finance public chart feed via GitHub Actions',
    'definition': 'Scheduled public-feed snapshot, approximately every two hours on weekdays. Actions and provider delays can occur. The browser checks this file every 60 seconds; that does not create minute-by-minute exchange data.',
    'feed_errors': failures}
if valid:
    previous_path.write_text(json.dumps(payload, indent=2, allow_nan=False))
else:
    print('All feeds failed; retaining the previous dated quote snapshot')
report = ROOT / 'tools/results/2026-09-30/quant-refresh.json'
report.parent.mkdir(parents=True, exist_ok=True)
report.write_bytes(gzip.decompress((ROOT / 'data/quant-snapshot.json.gz').read_bytes()))
ledger_path = DATA / 'forecast-monitor.json'
ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else None
if ledger is None or ledger.get('summary', {}).get('pending', 0) > 0:
    ledger = update_monitor(report_path=report, ledger_path=ledger_path, force=True)
    for row in ledger['records']:
        source = row.get('outcome_source')
        if row['status'] == 'scored' and source:
            origin = ROOT / 'tools' / source['raw_file']
            destination = DATA / 'provenance' / origin.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if origin.exists():
                shutil.copyfile(origin, destination)
                source['raw_url'] = 'data/provenance/' + destination.name
    ledger_path.write_text(json.dumps(ledger, indent=2, allow_nan=False))
print(json.dumps({'successful_quotes': len(valid), 'feed_errors': len(failures), 'forward_register': ledger['summary']}, indent=2))
