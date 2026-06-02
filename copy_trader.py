"""
Polymarket Paper Copy-Trading Monitor
Tracks 10 wallets via Polymarket Data API (public), simulates via pm-trader.
Usage: python copy_trader.py [--once] [--dry] [--interval 300]
"""
import subprocess, json, time, os, sys, io, threading
from datetime import datetime
from collections import defaultdict
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Safe print: won't crash on closed stdout (e.g., under Start-Process)
import builtins
_real_print = builtins.print
def _safe_print(*args, **kwargs):
    try: _real_print(*args, **kwargs)
    except: _real_print(*args, file=sys.stderr, **kwargs)
builtins.print = _safe_print

# ===== CONFIG =====
DATA_API = "https://data-api.polymarket.com"
PM_TRADER = "pm-trader"

# ===== CONFIG: read active wallets from JSON, fallback to defaults =====
DEFAULT_WALLETS = [
    {"addr": "0x15ceffed7bf820cd2d90f90ea24ae9909f5cd5fa", "name": "HondaCivic",      "cat": "Weather"},
    {"addr": "0x57ee70867b4e387de9de34fd62bc685aa02a8112", "name": "ikik111",         "cat": "Weather"},
    {"addr": "0x1f66796b45581868376365aef54b51eb84184c8d", "name": "Maskache2",       "cat": "Weather"},
    {"addr": "0x1838cca016850ac7185a9b149fe7d0bd2d6629b4", "name": "JoeMeteorolog",   "cat": "Weather"},
    {"addr": "0x331bf91c132af9d921e1908ca0979363fc47193f", "name": "BeefSlayer",      "cat": "Weather"},
    {"addr": "0xd75d96a23515172778d3281f53c9180b985100c8", "name": "Varyage",         "cat": "Weather"},
    {"addr": "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f", "name": "wokerjoesleeper", "cat": "Politics"},
    {"addr": "0x38e59b36aae31b164200d0cad7c3fe5e0ee795e7", "name": "cowcat",          "cat": "Politics"},
    {"addr": "0x07921379f7b31ef93da634b688b2fe36897db778", "name": "ewelmealt",       "cat": "Sports"},
    {"addr": "0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5", "name": "EFFICIENCYXPERT", "cat": "Sports"},
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.environ.get("STATE_FILE", os.path.join(BASE_DIR, "copy_trader_state.json"))
WALLETS_FILE = os.path.join(BASE_DIR, "wallets_active.json")

def load_wallets():
    if os.path.exists(WALLETS_FILE):
        try:
            with open(WALLETS_FILE) as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except: pass
    return DEFAULT_WALLETS

WALLETS = load_wallets()

def api_fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            s = json.load(f)
            # Ensure required keys exist
            s.setdefault('seen_txns', [])
            s.setdefault('sim_trades', [])
            s.setdefault('wallet_pnl', {})
            s.setdefault('last_scan', None)
            return s
    return {"seen_txns": [], "sim_trades": [], "wallet_pnl": {}, "last_scan": None}

def save_state(st):
    with open(STATE_FILE, 'w') as f: json.dump(st, f, indent=2, ensure_ascii=False)

def pm(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout.strip())
    except: return None

INITIAL_CAPITAL = 500.0

def ensure_account(acct):
    """Ensure account exists with $500, return current balance info."""
    bal = pm(f"{PM_TRADER} --account {acct} balance")
    if not bal or not bal.get('ok'):
        pm(f"{PM_TRADER} --account {acct} init --balance {INITIAL_CAPITAL}")
        return {"cash": INITIAL_CAPITAL, "total_value": INITIAL_CAPITAL, "pnl": 0}
    data = bal.get('data', {})
    return {"cash": data.get('cash', 0), "total_value": data.get('total_value', 0), "pnl": data.get('pnl', 0)}

PRICE_TOLERANCE = 0.05   # 5 cents drift ok for slow markets
PRICE_WAIT = 5           # seconds to wait
MAX_TRADES_PER_SCAN = 5  # process 5 newest per wallet
MONITOR_START = 1        # Will be set at startup, 1 = filter enabled
MONITOR_START = None     # set at startup, skip all trades before this

def get_midpoint(slug):
    """Get current YES/NO midpoint for a market."""
    r = pm(f"{PM_TRADER} price \"{slug}\"")
    if r and r.get('ok') and r.get('data'):
        prices = r['data']
        yes_p = prices.get('YES', prices.get('yes', None))
        no_p = prices.get('NO', prices.get('no', None))
        if yes_p is not None and no_p is not None:
            # Return the relevant side price
            return {'YES': yes_p, 'NO': no_p}
    return None

def place_limit(acct, slug, outcome, side, amount, price):
    """Place a GTC limit order. Returns order result or None."""
    cmd = f'{PM_TRADER} --account {acct} orders place "{slug}" "{outcome}" {side.lower()} {amount} {price} --type gtc'
    return pm(cmd)

def sim_trade(w, trade, dry_run=False, skip_wait=False, cached_mid=None):
    """Simulate a copy trade. skip_wait=True for batch trades from same wallet.
    cached_mid: reuse midpoint from previous trade (same wallet, same tick)."""
    acct = f"copy-{w['name']}"
    side = trade.get('side', 'BUY').upper()
    slug = trade.get('slug', '')
    outcome = trade.get('outcome', 'Yes')
    size = float(trade.get('size', 0))
    whale_price = float(trade.get('price', 0.5))

    pre_bal = ensure_account(acct)

    whale_notional = size * whale_price
    sim_usd = round(whale_notional * 0.02, 2)
    sim_usd = max(sim_usd, 1.0)
    sim_usd = min(sim_usd, INITIAL_CAPITAL * 0.05)

    ts = trade.get('timestamp', '')
    try: ts = datetime.utcfromtimestamp(int(ts)).isoformat() if ts else datetime.now().isoformat()
    except: ts = datetime.now().isoformat()

    base = {"account": acct, "wallet": w['name'], "category": w['cat'],
            "side": side, "size": size, "whale_price": whale_price, "slug": slug[:50],
            "outcome": outcome, "sim_usd": sim_usd, "pre_balance": pre_bal['total_value'],
            "timestamp": ts}

    if dry_run:
        return {**base, "status": "DRY_RUN"}

    trade_side = 'buy' if side == 'BUY' else 'sell'
    direction_str = '买入' if side == 'BUY' else '卖出'

    # STEP 1: Short wait
    if not skip_wait:
        time.sleep(PRICE_WAIT)

    # STEP 2: Market order (FOK) — gets immediate fill, captures real slippage
    if trade_side == 'buy':
        cmd = f'{PM_TRADER} --account {acct} buy "{slug}" "{outcome}" {sim_usd}'
    else:
        cmd = f'{PM_TRADER} --account {acct} sell "{slug}" "{outcome}" {sim_usd}'

    print(f"market {trade_side} ${sim_usd:.2f}", end=" ", flush=True)
    result = pm(cmd)

    post_bal = ensure_account(acct)

    if result and result.get('ok') and result.get('data',{}).get('trade'):
        trade_data = result['data']['trade']
        fill_price = trade_data.get('avg_price', whale_price)
        fill_shares = trade_data.get('shares', 0)
        fill_slippage = trade_data.get('slippage', 0)
        whale_slippage = round(abs(fill_price - whale_price), 4)
        whale_slippage_pct = round(whale_slippage / whale_price * 100, 2) if whale_price > 0 else 0

        # Track realized P&L (SELL only: compare to previous BUY cost basis)
        realized_delta = 0.0
        if side == 'SELL':
            pos_key = slug[:40]
            existing = base.get('_positions', {}).get(pos_key, {})
            cost_basis = existing.get('cost', fill_price)
            buy_shares = existing.get('shares', fill_shares)
            realized_delta = round((fill_price - cost_basis) * min(fill_shares, buy_shares), 4)

        print(f"FILLED @ {fill_price} (whale={whale_price} slip={whale_slippage} {whale_slippage_pct}%)")
        return {**base, "status": "FILLED", "fill_price": fill_price,
                "whale_slippage": whale_slippage, "whale_slippage_pct": whale_slippage_pct,
                "shares": fill_shares, "pm_slippage": fill_slippage,
                "realized_delta": realized_delta,
                "post_balance": post_bal['total_value'], "pnl": post_bal['pnl'], "result": result}
    else:
        err = str(result.get('error','')) if result else 'no response'
        if 'MARKET_NOT_FOUND' in err or 'not found' in err.lower():
            print(f"SKIP (closed)")
            return {**base, "status": "SKIPPED", "reason": "market_closed",
                    "post_balance": post_bal['total_value'], "pnl": post_bal['pnl']}
        if 'insufficient' in err.lower():
            print(f"SKIP (no funds)")
            return {**base, "status": "SKIPPED", "reason": "insufficient_funds",
                    "post_balance": post_bal['total_value'], "pnl": post_bal['pnl']}
        print(f"FAIL ({err[:30]})")
        return {**base, "status": "FAILED", "reason": err[:50],
                "post_balance": post_bal['total_value'], "pnl": post_bal['pnl']}

def get_all_pnl(realized_tracker=None):
    """Query P&L for all wallet accounts. Includes realized P&L from tracker."""
    pnl_data = {}
    for w in WALLETS:
        acct = f"copy-{w['name']}"
        bal = ensure_account(acct)
        realized = realized_tracker.get(w['name'], 0.0) if realized_tracker else 0.0
        total_val = round(bal['total_value'], 2)
        cash_val = round(bal['cash'], 2)
        unrealized = round(total_val - cash_val - realized, 2)
        pnl_data[w['name']] = {
            "wallet": w['name'],
            "category": w['cat'],
            "capital": INITIAL_CAPITAL,
            "cash": cash_val,
            "total_value": total_val,
            "pnl": round(bal['pnl'], 2),
            "pnl_pct": round((total_val - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2),
            "realized": round(realized, 2),
            "unrealized": unrealized,
        }
    return pnl_data

def main():
    global WALLETS
    dry_run = '--dry' in sys.argv
    once = '--once' in sys.argv
    interval = 120
    for i, a in enumerate(sys.argv):
        if a == '--interval' and i+1 < len(sys.argv): interval = int(sys.argv[i+1])

    print("\n" + "=" * 72)
    print("  Polymarket Paper Copy-Trading Monitor")
    print("  10 wallets: 6 Weather + 2 Politics + 2 Sports")
    print(f"  Data API: {DATA_API}")
    print(f"  Sim mode: {'DRY RUN (no trades)' if dry_run else 'PAPER TRADING'}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    # P&L already snapshotted above, reload for consistency
    state = load_state()

    print(f"\n  {'#':<3} {'Name':<18} {'Category':<10} {'Profile URL':<50}")
    print(f"  {'-'*3} {'-'*18} {'-'*10} {'-'*50}")
    for i, w in enumerate(WALLETS):
        url = f"https://polymarket.com/@/{w['name']}"
        note = w.get('note', '')
        print(f"  {i+1:<3} {w['name']:<18} {w['cat']:<10} {url:<50} {note}")

    total_new = 0
    scan_count = 0
    realized_pnl = state.get('realized_pnl', {})  # per-wallet realized P&L

    SCAN_INTERVAL = interval
    while True:
        scan_count += 1
        scan_start = datetime.now()
        print(f"\n  --- Scan #{scan_count} {scan_start.strftime('%H:%M:%S')} ---")

        # Reload wallet list from config (allows dashboard add/remove without restart)
        old_wallets = {w['name'] for w in WALLETS}
        new_wallets = load_wallets()
        new_names = {w['name'] for w in new_wallets}
        added = new_names - old_wallets
        removed = old_wallets - new_names
        if added:
            print(f"  + Added wallets: {added}")
            for name in added:
                ensure_account(f"copy-{name}")
        if removed:
            print(f"  - Removed wallets: {removed}")
        if added or removed:
            print(f"  Wallets: {len(WALLETS)} → {len(new_wallets)}")
        WALLETS = new_wallets

        # Update last_scan at START so dashboard shows activity immediately
        state['last_scan'] = scan_start.strftime('%Y-%m-%d %H:%M:%S')
        save_state(state)

        for i, w in enumerate(WALLETS):
            try:
                url = f"{DATA_API}/trades?user={w['addr']}&limit=15"
                trades = api_fetch(url)
            except Exception as e:
                print(f"  [{i+1:02d}/10] {w['name']:<16} API error: {e}")
                continue

            new_trades = []
            last_mid = None  # batch: reuse midpoint for same-wallet trades
            for t in (trades or []):
                txn_hash = t.get('transactionHash', '')
                # Skip already processed
                if not txn_hash or txn_hash in state['seen_txns']:
                    continue
                # Skip trades older than monitor start (0 = disabled)
                trade_ts = int(t.get('timestamp', 0))
                if MONITOR_START and MONITOR_START > 0 and trade_ts < MONITOR_START:
                    state['seen_txns'].append(txn_hash)  # mark as seen but don't process
                    continue
                new_trades.append(t)

            # Only process the newest N trades per wallet
            if len(new_trades) > MAX_TRADES_PER_SCAN:
                new_trades = new_trades[-MAX_TRADES_PER_SCAN:]

            if new_trades:
                tag = w['cat'][:3]
                print(f"  [{i+1:02d}/10] {w['name']:<16} [{tag}] {len(new_trades)} new trade(s)")

                for j, tr in enumerate(new_trades):
                    side = tr.get('side', '?')
                    size = float(tr.get('size', 0))
                    price = float(tr.get('price', 0))
                    title = (tr.get('title', ''))[:50]
                    outcome = tr.get('outcome', '?')
                    slug = tr.get('slug', '')

                    print(f"         {side:5s} {size:>8.2f} x ${price:<8.4f} | {outcome:5s} | {title}")

                    sim = sim_trade(w, tr, dry_run=dry_run,
                                    skip_wait=(j > 0), cached_mid=last_mid)
                    if sim:
                        # Accumulate realized P&L from SELL fills
                        rd = sim.get('realized_delta', 0)
                        if rd != 0:
                            realized_pnl[w['name']] = realized_pnl.get(w['name'], 0.0) + rd
                        if sim.get('current_mid'): last_mid = sim['current_mid']
                        status = sim.get('status', '?')
                        if status == 'DRY_RUN':
                            print(f"         -> [DRY] ${sim['sim_usd']:.2f}")
                        elif status == 'HISTORICAL':
                            print(f"         -> [HIST] recorded (past trade)")
                        elif status == 'SKIPPED':
                            print(f"         -> [SKIP] {sim.get('reason','')}")
                        elif status == 'LIMIT_PLACED':
                            drift_s = f"drift={sim.get('drift',0):.3f}" if sim.get('drift') else ""
                            print(f"         -> [LIMIT] ${sim['sim_usd']:.2f} @ {sim.get('whale_price','?')} {drift_s}")
                        elif status == 'FAILED':
                            print(f"         -> [FAIL] {sim.get('reason','')}")
                        else:
                            print(f"         -> [{status}] ${sim['sim_usd']:.2f}")

                    state['seen_txns'].append(txn_hash)
                    state['sim_trades'].append(sim)
                    total_new += 1
                    # Update timestamp mid-scan so dashboard stays responsive
                    state['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if total_new % 3 == 0: save_state(state)

                if new_trades: save_state(state)
            # Wallet done, brief status
            if not new_trades:
                pass  # silent for no trades

        # Summary + P&L snapshot (quick: only if new trades, else skip pm-trader calls)
        txn_count = len(state['seen_txns'])
        sim_count = len(state['sim_trades'])
        elapsed = (datetime.now() - scan_start).total_seconds()

        # Full P&L refresh every 3rd scan, or if new trades found
        if total_new > 0 or scan_count % 3 == 0:
            state['wallet_pnl'] = get_all_pnl(realized_pnl)
            state['realized_pnl'] = dict(realized_pnl)

        state['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_state(state)
        print(f"\n  {'─'*50}")
        print(f"  Scan done in {elapsed:.1f}s | Captured: {txn_count} | Simulated: {sim_count} | New: {total_new}")
        if state.get('wallet_pnl'):
            print(f"\n  Wallet P&L (${INITIAL_CAPITAL} each):")
            for name, p in sorted(state['wallet_pnl'].items(), key=lambda x: x[1]['pnl_pct'], reverse=True):
                sign = '+' if p['pnl'] >= 0 else ''
                print(f"    {name:<18} ${p['total_value']:>8.2f} | {sign}{p['pnl_pct']:.2f}%")

        # Stats by wallet
        if sim_count > 0:
            by_w = defaultdict(lambda: {"count": 0, "buy": 0, "sell": 0, "buy_usd": 0, "sell_usd": 0})
            for tr in state['sim_trades']:
                bw = by_w[tr['wallet']]
                bw['count'] += 1
                if tr['side'] == 'BUY':
                    bw['buy'] += 1
                    bw['buy_usd'] += tr['sim_usd']
                else:
                    bw['sell'] += 1
                    bw['sell_usd'] += tr['sim_usd']

            print(f"\n  Copy Trading Summary:")
            print(f"  {'Wallet':<18} {'Trades':<8} {'Buy':<6} {'Sell':<6} {'Sim Buy$':<12} {'Sim Sell$':<12}")
            print(f"  {'─'*18} {'─'*8} {'─'*6} {'─'*6} {'─'*12} {'─'*12}")
            for name, st in sorted(by_w.items(), key=lambda x: x[1]['count'], reverse=True):
                print(f"  {name:<18} {st['count']:<8} {st['buy']:<6} {st['sell']:<6} ${st['buy_usd']:>10.2f} ${st['sell_usd']:>10.2f}")

        if once: break
        print(f"\n  Next scan in {interval}s...")
        time.sleep(interval)


if __name__ == '__main__':
    import threading
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    # Start mini HTTP server for dashboard
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=BASE_DIR, **kwargs)
        def log_message(self, format, *args): pass  # silent
        def do_POST(self):
            if self.path == '/save_wallets':
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    with open(WALLETS_FILE, 'w') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    global WALLETS
                    WALLETS = data
                    self.send_response(200)
                    self.send_header('Content-Type','application/json')
                    self.send_header('Access-Control-Allow-Origin','*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok":True,"count":len(data)}).encode())
                except Exception as e:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            else:
                self.send_response(404); self.end_headers()
        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Content-Type')
            self.end_headers()

    httpd = HTTPServer(('0.0.0.0', 8766), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    import copy_trader
    copy_trader.MONITOR_START = int(datetime.now().timestamp())

    # Use sys.stderr to avoid I/O errors from closed stdout under Start-Process
    import sys as _sys
    _sys.stderr.write(f"\n  Dashboard: http://localhost:8766/copy_dashboard.html\n")
    _sys.stderr.write(f"  Monitor start: {datetime.fromtimestamp(copy_trader.MONITOR_START).strftime('%Y-%m-%d %H:%M:%S')}\n")
    _sys.stderr.write(f"  Only new trades from now. Historical data ignored.\n\n")

    old_state = load_state()
    realized_init = old_state.get('realized_pnl', {})

    state = {"seen_txns": [], "sim_trades": [], "wallet_pnl": {}, "last_scan": None,
             "monitor_start": datetime.fromtimestamp(copy_trader.MONITOR_START).strftime('%Y-%m-%d %H:%M:%S')}
    state['wallet_pnl'] = get_all_pnl(realized_init)
    state['realized_pnl'] = dict(realized_init)
    state['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_state(state)

    try:
        main()
    except KeyboardInterrupt:
        _sys.stderr.write("\n\n  Stopped.\n")
        httpd.shutdown()
        save_state(load_state())
