"""Summary / aggregate API."""
from fastapi import APIRouter
from database import get_db
from config import INITIAL_CAPITAL

router = APIRouter(prefix="/api", tags=["summary"])

@router.get("/summary")
def get_summary():
    db = get_db()
    wallets = db.execute("SELECT id FROM wallets WHERE active = 1").fetchall()

    total_cash = 0.0
    total_value = 0.0
    wallet_count = 0

    for w in wallets:
        pnl = db.execute(
            "SELECT cash, total_value FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
            (w["id"],)
        ).fetchone()
        if pnl:
            total_cash += pnl["cash"] or 0
            total_value += pnl["total_value"] or 0
            wallet_count += 1

    total_capital = INITIAL_CAPITAL * wallet_count

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

@router.get("/summary/segments")
def get_pnl_segments():
    """P&L breakdown: today / this week / this month."""
    db = get_db()
    wallets = db.execute("SELECT id FROM wallets WHERE active = 1").fetchall()
    wallet_ids = [w['id'] for w in wallets]
    if not wallet_ids:
        return {"today": 0, "week": 0, "month": 0}
    placeholders = ','.join('?' for _ in wallet_ids)

    def segment_since(since_expr):
        rows = db.execute(f"""
            SELECT wallet_id, MIN(total_value) as first_val, MAX(total_value) as last_val FROM (
                SELECT wallet_id, total_value,
                       ROW_NUMBER() OVER (PARTITION BY wallet_id ORDER BY id ASC) as rn_asc,
                       ROW_NUMBER() OVER (PARTITION BY wallet_id ORDER BY id DESC) as rn_desc
                FROM pnl_snapshots
                WHERE wallet_id IN ({placeholders}) AND timestamp >= {since_expr}
            ) WHERE rn_asc = 1 OR rn_desc = 1
            GROUP BY wallet_id
        """, wallet_ids).fetchall()
        pnl = 0.0
        for r in rows:
            if r['first_val'] and r['last_val']:
                pnl += r['last_val'] - r['first_val']
        return round(pnl, 2)

    return {
        "today": segment_since("datetime('now','localtime','start of day')"),
        "week": segment_since("datetime('now','localtime','weekday 0','-7 days')"),
        "month": segment_since("datetime('now','localtime','start of month')"),
    }

@router.get("/summary/compare")
def get_wallet_compare():
    """P&L history for all active wallets (for comparison chart)."""
    db = get_db()
    wallets = db.execute("SELECT id, name FROM wallets WHERE active = 1 ORDER BY name").fetchall()
    series = []
    for w in wallets:
        rows = db.execute("""
            SELECT pnl_pct, timestamp FROM pnl_snapshots
            WHERE wallet_id = ? ORDER BY timestamp ASC
        """, (w['id'],)).fetchall()
        if rows:
            series.append({
                "name": w['name'],
                "points": [{"t": r['timestamp'][:16], "v": r['pnl_pct']} for r in rows]
            })
    return series


@router.get("/summary/success-rate")
def get_success_rate():
    """Per-wallet trade success rate: FILLED vs SKIPPED breakdown."""
    db = get_db()
    wallets = db.execute("SELECT id, name FROM wallets WHERE active = 1 ORDER BY name").fetchall()

    result = []
    for w in wallets:
        wid = w["id"]
        total = db.execute("SELECT COUNT(*) FROM trade_log WHERE wallet_id = ?", (wid,)).fetchone()[0]
        filled = db.execute(
            "SELECT COUNT(*) FROM trade_log WHERE wallet_id = ? AND status = 'FILLED'", (wid,)
        ).fetchone()[0]
        skipped = db.execute(
            "SELECT COUNT(*) FROM trade_log WHERE wallet_id = ? AND status = 'SKIPPED'", (wid,)
        ).fetchone()[0]
        failed = db.execute(
            "SELECT COUNT(*) FROM trade_log WHERE wallet_id = ? AND status = 'FAILED'", (wid,)
        ).fetchone()[0]

        # Breakdown of skip reasons
        skip_breakdown = {}
        reasons = db.execute("""
            SELECT skip_reason, COUNT(*) as cnt FROM trade_log
            WHERE wallet_id = ? AND status = 'SKIPPED' AND skip_reason IS NOT NULL
            GROUP BY skip_reason ORDER BY cnt DESC
        """, (wid,)).fetchall()
        for r in reasons:
            skip_breakdown[r["skip_reason"]] = r["cnt"]

        # Win/loss within FILLED
        wins = db.execute(
            "SELECT COUNT(*) FROM trade_log WHERE wallet_id = ? AND status = 'FILLED' AND pnl_realized > 0",
            (wid,)
        ).fetchone()[0]
        losses = db.execute(
            "SELECT COUNT(*) FROM trade_log WHERE wallet_id = ? AND status = 'FILLED' AND pnl_realized < 0",
            (wid,)
        ).fetchone()[0]

        success_rate = round(filled / total * 100, 1) if total > 0 else None

        result.append({
            "wallet_id": wid,
            "name": w["name"],
            "total": total,
            "filled": filled,
            "skipped": skipped,
            "failed": failed,
            "success_rate": success_rate,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / filled * 100, 1) if filled > 0 else None,
            "skip_reasons": skip_breakdown,
        })

    # Sort by total trades desc
    result.sort(key=lambda x: x["total"], reverse=True)
    return result
