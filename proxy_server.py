"""
TradingAgents Workbench - Local Data Proxy
Serves Yahoo Finance data without CORS issues.
Usage: python proxy_server.py
Then open tradingagents-workbench.html
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse
import ssl
import re

PORT = 8765

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)

        # CORS headers
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

        try:
            if path == '/search':
                self.handle_search(params)
            elif path.startswith('/price/'):
                ticker = path.split('/price/')[1].strip()
                self.handle_price(ticker)
            elif path == '/health':
                self.wfile.write(json.dumps({'status':'ok'}).encode())
            else:
                self.wfile.write(json.dumps({'error':'unknown endpoint'}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def handle_search(self, params):
        q = params.get('q', [''])[0]
        if not q:
            self.wfile.write(json.dumps([]).encode())
            return
        url = f'https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(q)}&lang=en-US&region=US&quotesCount=10'
        data = self._fetch(url)
        quotes = json.loads(data).get('quotes', [])
        results = [
            {'ticker': i.get('symbol',''), 'name': i.get('shortname') or i.get('longname',''), 'exchange': i.get('exchange','')}
            for i in quotes if i.get('quoteType') in ('EQUITY','ETF')
        ]
        self.wfile.write(json.dumps(results, ensure_ascii=False).encode())

    def handle_price(self, ticker):
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?interval=1d&range=1d'
        data = self._fetch(url)
        meta = json.loads(data).get('chart',{}).get('result',[{}])[0].get('meta',{})
        result = {
            'ticker': ticker,
            'price': meta.get('regularMarketPrice'),
            'prev_close': meta.get('previousClose'),
            'currency': meta.get('currency','USD'),
        }
        self.wfile.write(json.dumps(result).encode())

    def _fetch(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            return resp.read()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[proxy] {args[0]}")

if __name__ == '__main__':
    print(f'◆ TradingAgents Data Proxy ◆')
    print(f'  Listening on http://localhost:{PORT}')
    print(f'  Endpoints:')
    print(f'    GET /search?q=AAPL    - Search tickers')
    print(f'    GET /price/AAPL       - Get current price')
    print(f'    GET /health           - Health check')
    print()
    server = HTTPServer(('127.0.0.1', PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()
