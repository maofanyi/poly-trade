"""Summary / aggregate API."""
from fastapi import APIRouter
from database import get_db
from config import INITIAL_CAPITAL

router = APIRouter(prefix="/api", tags=["summary"])

@router.get("/summary")
def get_summary():
    db = get_db()
    wallets = db.execute("SELECT id FROM wallets WHERE active = 1").fetchall()

    wallet_count = len(wallets)
    total_capital = INITIAL_CAPITAL * wallet_count

    total_cash = 0.0
    total_value = 0.0

    for w in wallets:
        pnl = db.execute(
            "SELECT cash, total_value FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
            (w["id"],)
        ).fetchone()
        if pnl:
            total_cash += pnl["cash"] or 0
            total_value += pnl["total_value"] or 0

    total_pnl = round(total_value - total_capital, 2)
    total_pnl_pct = round(total_pnl / total_capital * 100, 2) if total_capital > 0 else 0.0

    total_trades = db.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    filled = db.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'FILLED'").fetchone()[0]
    wins = db.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'FILLED' AND pnl_realized > 0").fetchone()[0]
    win_rate = round(wins / filled * 100, 2) if filled > 0 else None

    last_scan = db.execute("SELECT scan_end FROM scan_log ORDER BY id DESC LIMIT 1").fetchone()

    return {
        "total_capital": total_capital,
        "total_cash": round(total_cash, 2),
        "total_value": round(total_value, 2),
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "wallet_count": wallet_count,
        "active_wallet_count": wallet_count,
        "last_scan": last_scan["scan_end"] if last_scan else None,
        "total_trades": total_trades,
        "win_rate": win_rate
    }
