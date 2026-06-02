"""Scanner unit tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = ":memory:"
os.environ["SCAN_ENABLED"] = "0"

from database import init_db, get_db
from scanner import is_txn_seen, log_trade, get_cost_basis

def test_is_txn_seen():
    init_db()
    db = get_db()
    db.execute("DELETE FROM trade_log")
    db.execute("DELETE FROM wallets")
    db.commit()
    db.execute("INSERT INTO wallets (id, address, name) VALUES (1, '0xtest', 'Test')")
    db.commit()

    assert not is_txn_seen(db, '0xabc123')

    log_trade(db, 1, txn_hash='0xabc123', side='BUY', size=10, whale_price=0.5, sim_usd=2, fill_price=0.51, status='FILLED', slippage=0.01, pnl_realized=0, slug='test-market', outcome='Yes', timestamp='2026-01-01')

    assert is_txn_seen(db, '0xabc123')

def test_get_cost_basis():
    init_db()
    db = get_db()
    db.execute("DELETE FROM trade_log")
    db.execute("DELETE FROM wallets")
    db.execute("INSERT INTO wallets (id, address, name) VALUES (1, '0xtest2', 'Test2')")
    db.commit()

    log_trade(db, 1, txn_hash='0xbuy1', side='BUY', size=100, whale_price=0.5, sim_usd=10, fill_price=0.55, status='FILLED', slippage=0, pnl_realized=0, slug='my-market', outcome='Yes', timestamp='2026-01-01')

    cost, shares = get_cost_basis(db, 1, 'my-market')
    assert cost == 0.55
    assert shares == 100

    cost, shares = get_cost_basis(db, 1, 'nonexistent')
    assert cost == 0

def test_sell_without_position_is_skipped():
    """Verify has_position returns False for a fresh account with no trades."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ["DB_PATH"] = ":memory:"
    os.environ["SCAN_ENABLED"] = "0"
    from database import init_db, get_db
    from trader import has_position
    init_db()
    db = get_db()
    db.execute("DELETE FROM trade_log")
    db.execute("DELETE FROM wallets")
    db.commit()
    db.execute("INSERT INTO wallets (id, address, name) VALUES (1, '0xatest', 'ATest')")
    db.commit()
    assert not has_position('copy-ATest', 'some-market', 'Yes')
