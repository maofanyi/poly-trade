"""Automated tests for copy_trader pipeline."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copy_trader import *

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")

def test_wallet_loading():
    print("\n--- Wallet Loading ---")
    wallets = load_wallets()
    check("load_wallets returns list", isinstance(wallets, list))
    check("at least 10 wallets", len(wallets) >= 10)
    check("each wallet has addr/name/cat", all('addr' in w and 'name' in w and 'cat' in w for w in wallets))
    check("no duplicate addresses", len(set(w['addr'] for w in wallets)) == len(wallets))

def test_state_persistence():
    print("\n--- State Persistence ---")
    # Save dummy state
    test_state = {
        "seen_txns": ["0xtest1", "0xtest2"],
        "sim_trades": [{"wallet": "test", "side": "BUY", "status": "FILLED"}],
        "wallet_pnl": {"test": {"wallet": "test", "category": "Crypto", "capital": 500, "cash": 490, "total_value": 510, "pnl": 10, "pnl_pct": 2.0}},
        "last_scan": "2026-06-02 15:00:00"
    }
    save_state(test_state)
    loaded = load_state()
    check("state save/load roundtrip", loaded['seen_txns'] == test_state['seen_txns'])
    check("wallet_pnl preserved", len(loaded.get('wallet_pnl', {})) == 1)
    # Cleanup
    os.remove(STATE_FILE)

def test_price_check():
    print("\n--- Price Fetch ---")
    # Test fetching price for known active market
    price = fetchPrice("BTC-USD")
    check("BTC-USD price fetchable", price is not None and price > 0, f"got {price}")

    # Test invalid ticker
    price2 = fetchPrice("ZZZZZZ-NOTREAL")
    check("invalid ticker returns null", price2 is None)

def test_data_api():
    print("\n--- Data API ---")
    import urllib.request
    # Test data API is accessible
    try:
        url = f"{DATA_API}/trades?user=0xe1D6b51521Bd4365769199f392F9818661BD907c&limit=3"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        check("Data API accessible", isinstance(data, list))
        check("Returns trade data", len(data) > 0)
        if data:
            check("Trade has required fields", all(k in data[0] for k in ['side','price','size','slug','transactionHash']))
    except Exception as e:
        check("Data API accessible", False, str(e)[:80])

def test_pm_trader():
    print("\n--- pm-trader CLI ---")
    # Test account init
    test_acct = "copy-test-automated"
    r = pm(f"{PM_TRADER} --account {test_acct} reset --confirm")
    r = pm(f"{PM_TRADER} --account {test_acct} init --balance 500")
    check("account init", r and r.get('ok'))

    r = pm(f"{PM_TRADER} --account {test_acct} balance")
    check("balance check", r and r.get('ok') and r['data']['cash'] == 500, str(r)[:80])

    # Test market list
    r = pm(f"{PM_TRADER} markets list --limit 1 --sort-by volume")
    check("market list", r and r.get('ok') and len(r.get('data',[])) > 0)

    # Cleanup test account
    pm(f"{PM_TRADER} --account {test_acct} reset --confirm")

def test_json_build():
    print("\n--- JSON Build ---")
    # simulate buildJSON() logic
    holdings = [{"ticker": "AAPL", "shares": 10, "cost": 150, "current_price": 155}]
    total_mkt = sum(h['shares'] * h['current_price'] for h in holdings)
    total_cost = sum(h['shares'] * h['cost'] for h in holdings)
    check("market value calc", total_mkt == 1550)
    check("pnl calc", round((total_mkt - total_cost) / total_cost * 100, 2) == 3.33)

def run_all():
    global PASS, FAIL
    PASS = FAIL = 0
    print("=" * 60)
    print("  copy_trader Automated Tests")
    print("=" * 60)

    tests = [test_wallet_loading, test_state_persistence, test_data_api, test_pm_trader]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAIL += 1
            print(f"  [CRASH] {t.__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print(f"{'='*60}")
    return FAIL == 0

if __name__ == '__main__':
    ok = run_all()
    sys.exit(0 if ok else 1)
