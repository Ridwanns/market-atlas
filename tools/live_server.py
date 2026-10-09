"""Loopback-only dashboard and timestamped public-feed quote service.

No brokerage credentials, transactions, arbitrary URLs or filesystem serving.
"""
import concurrent.futures
import datetime as dt
import json
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from forecast_monitor import update_monitor

ROOT = Path(__file__).resolve().parent
PORT = 8767
WIB = dt.timezone(dt.timedelta(hours=7))
SYMBOLS = ['NVDA', 'TSM', 'MU', 'SPY', '^GSPC', '^IXIC', '^JKSE', 'IDR=X']
STATE = {'data': None, 'expires': 0}
LOCK = threading.Lock()

def iso(stamp, zone=dt.timezone.utc):
    return dt.datetime.fromtimestamp(stamp, zone).isoformat()

def fetch_quote(symbol):
    url = ('https://query1.finance.yahoo.com/v8/finance/chart/' +
           urllib.parse.quote(symbol, safe='') + '?range=1d&interval=1m&includePrePost=true')
    captured = time.time()
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            parsed = json.load(response)
        chart = parsed['chart']['result'][0]
        meta = chart['meta']
        price = meta['regularMarketPrice']
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError('Missing positive last price')
        regular_time = meta['regularMarketTime']
        quote_series = chart.get('indicators', {}).get('quote') or [{}]
        closes = quote_series[0].get('close') or []
        bars = [(t, p) for t, p in zip(chart.get('timestamp') or [], closes)
                if p is not None and p > 0]
        latest_time, latest_price = bars[-1] if bars else (regular_time, price)
        periods = meta.get('currentTradingPeriod', {})
        session = 'Closed'
        for period, label in [('pre', 'Pre-market'), ('regular', 'Regular session'), ('post', 'After hours')]:
            bounds = periods.get(period, {})
            if bounds.get('start', float('inf')) <= captured < bounds.get('end', 0):
                session = label
        if symbol == 'IDR=X':
            session = 'FX feed'
        # Range/interval responses occasionally end before the newest regular quote.
        if regular_time > latest_time:
            latest_time, latest_price = regular_time, price
        step = max(1, len(bars) // 300)
        sampled = bars[::step]
        if bars and (not sampled or sampled[-1] != bars[-1]):
            sampled.append(bars[-1])
        previous = meta.get('previousClose', meta.get('chartPreviousClose'))
        return {'symbol': symbol, 'price': price, 'currency': meta.get('currency'),
                'quote_time_utc': iso(regular_time), 'quote_time_wib': iso(regular_time, WIB),
                'captured_utc': iso(captured), 'captured_wib': iso(captured, WIB),
                'previous_close': previous, 'session': session,
                'exchange': meta.get('fullExchangeName', meta.get('exchangeName')),
                'provider_delay_minutes': meta.get('exchangeDataDelayedBy'), 'source_url': url,
                'latest_minute_bar': {'price': latest_price, 'time_utc': iso(latest_time),
                    'observation_type': 'minute bar' if bars else 'regular quote fallback; minute bars unavailable',
                    'time_wib': iso(latest_time, WIB), 'age_minutes_at_capture': max(0, (captured-latest_time)/60),
                    'after_regular_session': latest_time >= periods.get('regular', {}).get('end', float('inf'))},
                'intraday': [{'time': iso(t), 'price': p} for t, p in sampled]}
    except Exception as exc:
        return {'symbol': symbol, 'error': str(exc)[:300], 'captured_utc': iso(captured), 'source_url': url}

def quotes():
    with LOCK:
        if STATE['data'] is None or time.monotonic() >= STATE['expires']:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                rows = list(pool.map(fetch_quote, SYMBOLS))
            stamp = time.time()
            data = {'fetched_utc': iso(stamp), 'fetched_wib': iso(stamp, WIB), 'quotes': rows,
                    'refresh_seconds': 60, 'provider': 'Yahoo Finance public chart feed',
                    'definition': 'Automatically retrieved last prices and minute bars; exchange delay varies. Not executable bid/ask or a guaranteed real-time exchange feed. Historical models and financials are unchanged.'}
            STATE.update(data=data, expires=time.monotonic()+55)
            folder = ROOT/'results/live'
            folder.mkdir(parents=True, exist_ok=True)
            (folder/'latest-quotes.json').write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
        return STATE['data']

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_payload_headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        origin = self.headers.get('Origin')
        allowed = {'null', f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'}
        if origin in allowed:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def do_OPTIONS(self):
        self.send_payload_headers(204, 'text/plain', 0)

    def do_GET(self):
        # Exact routes only: the service cannot expose other project files.
        route = urllib.parse.urlsplit(self.path).path
        if route == '/api/health':
            body = json.dumps({'ok': True, 'service': 'market-atlas-live', 'port': PORT}).encode()
            content_type, status = 'application/json', 200
        elif route == '/api/quotes':
            body = json.dumps(quotes(), allow_nan=False).encode()
            content_type = 'application/json'
            status = 200 if any('error' not in q for q in STATE['data']['quotes']) else 503
        elif route == '/api/forecast-monitor':
            try:
                body = json.dumps(update_monitor(), allow_nan=False).encode()
                content_type, status = 'application/json', 200
            except Exception as exc:
                body = json.dumps({'error': str(exc)[:300]}).encode()
                content_type, status = 'application/json', 503
        elif route in ['/', '/combined-market-report.html']:
            body = (ROOT/'combined-market-report.html').read_bytes()
            content_type, status = 'text/html; charset=utf-8', 200
        else:
            body, content_type, status = b'Not found', 'text/plain', 404
        self.send_payload_headers(status, content_type, len(body))
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

if __name__ == '__main__':
    print(f'Market Atlas live dashboard: http://127.0.0.1:{PORT}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
