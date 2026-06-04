"""Long-running local integration test — starts app + scanner, verifies FILLED trades."""
import os, sys, time, json, threading
import urllib.request
from unittest.mock import patch, MagicMock

sys.path.insert(0, '.')

PORT = 18767
BASE_URL = f'http://127.0.0.1:{PORT}'

# Generate fake trades for multiple wallets across multiple scans
WALLET_TRADES = {
    'TestWallet1': [
        {'transactionHash': '0xA1', 'side': 'BUY', 'size': 200, 'price': 0.55,
         'timestamp': int(time.time()), 'slug': 'btc-100k-2026', 'outcome': 'Yes', 'title': 'BTC 100k'},
    ],
    'TestWallet2': [
        {'transactionHash': '0xB1', 'side': 'BUY', 'size': 300, 'price': 0.40,
         'timestamp': int(time.time()), 'slug': 'eth-above-5k-2026', 'outcome': 'No', 'title': 'ETH 5k'},
    ],
}

# Mock subprocess for pm-trader
def mock_subprocess(cmd, shell=True, capture_output=True, text=True, timeout=15):
    m = MagicMock()
    if 'balance' in cmd: m.stdout = '{"ok":true,"data":{"cash":500,"total_value":500,"pnl":0}}'
    elif 'portfolio' in cmd: m.stdout = '{"ok":true,"data":[]}'
    elif 'price' in cmd:
        if 'btc' in cmd: m.stdout = '{"ok":true,"data":{"YES":0.55,"NO":0.45}}'
        else: m.stdout = '{"ok":true,"data":{"YES":0.42,"NO":0.58}}'
    elif 'buy' in cmd: m.stdout = '{"ok":true,"data":{"trade":{"avg_price":0.50,"shares":10}}}'
    elif 'sell' in cmd: m.stdout = '{"ok":true,"data":{"trade":{"avg_price":0.50,"shares":10}}}'
    else: m.stdout = '{"ok":true,"data":{}}'
    return m

# Mock api_fetch to return canned trades matching wallet address
REAL_API = urllib.request.urlopen

def mock_api(url, *args, **kwargs):
    """Return canned trades based on wallet address in URL."""
    for name, trades in WALLET_TRADES.items():
        # Address is '0x'+name (simplified)
        addr = f'0x{name}'
        if addr in url:
            resp = MagicMock()
            resp.read.return_value = json.dumps(trades).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = lambda s,*a: None
            return resp
    # Fallback to empty
    resp = MagicMock()
    resp.read.return_value = json.dumps([]).encode()
    return resp

def setup_app():
    """Configure DB and start FastAPI app."""
    db_path = f'G:/trade/data/test_longrun_{os.getpid()}.db'
    os.environ['DB_PATH'] = db_path
    os.environ['SCAN_ENABLED'] = '1'
    os.environ['SCAN_INTERVAL'] = '2'

    from database import init_db, get_db
    init_db()
    db = get_db()

    # Clean state
    db.execute('DELETE FROM closed_markets')
    db.execute('DELETE FROM positions')
    db.execute('DELETE FROM trade_log')
    db.execute('DELETE FROM wallet_scores')
    db.execute('DELETE FROM discovered_wallets')
    db.commit()

    # Seed test wallets matching WALLET_TRADES
    for name in WALLET_TRADES:
        db.execute(
            "INSERT OR IGNORE INTO wallets (name, address, category) VALUES (?, ?, ?)",
            (name, f'0x{name}', 'Weather')
        )
    db.commit()

    return db, db_path

def cleanup(db, db_path):
    """Close DB and remove temp files."""
    db.close()
    for ext in ['', '-wal', '-shm', '-journal']:
        try: os.remove(f'{db_path}{ext}')
        except: pass

def test_long_running_scanner():
    """Run the app for 15 seconds and verify FILLED trades appear."""
    db, db_path = setup_app()

    # Patch api_fetch AND start FastAPI
    # We use a simpler approach: patch scanner.api_fetch globally
    with patch('scanner.api_fetch', side_effect=lambda url: [
        t for name, trades in WALLET_TRADES.items()
        for t in trades if f'0x{name}' in url
    ] or []):
        with patch('subprocess.run', side_effect=mock_subprocess):
            from scanner import scan_loop, set_ws_manager
            class FakeWS:
                async def broadcast(self, m): pass
            set_ws_manager(FakeWS())

            t = threading.Thread(target=scan_loop, daemon=True)
            t.start()

            print('Scanner started, waiting 15s...')
            start = time.time()
            while time.time() - start < 15:
                time.sleep(1)

            # Check results
            from database import get_db as gdb
            db2 = gdb()
            trades = db2.execute(
                "SELECT status, side, sim_usd, slug FROM trade_log ORDER BY id"
            ).fetchall()

            filled = [t for t in trades if t['status'] == 'FILLED']
            synced = [t for t in trades if t['status'] == 'SYNCED']
            skipped = [t for t in trades if t['status'] == 'SKIPPED']
            failed = [t for t in trades if t['status'] == 'FAILED']

            print(f'Results after 15s:')
            print(f'  FILLED: {len(filled)}')
            print(f'  SYNCED: {len(synced)}')
            print(f'  SKIPPED: {len(skipped)}')
            print(f'  FAILED: {len(failed)}')

            for f in filled:
                print(f'    {f["side"]} ${f["sim_usd"]:.2f} {f["slug"][:30]}')

            # Check scan_log
            scan_statuses = db2.execute(
                "SELECT status, new_trades_found FROM scan_log ORDER BY id DESC LIMIT 5"
            ).fetchall()
            for s in scan_statuses:
                print(f'  scan_log: status={s["status"]} new={s["new_trades_found"]}')

            assert len(filled) > 0, "Expected at least 1 FILLED trade after 15s of scanning"
            print('\nPASS: Long-running scanner produces FILLED trades')

    cleanup(db, db_path)

if __name__ == '__main__':
    test_long_running_scanner()
