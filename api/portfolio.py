"""Portfolio analysis: exposure, overlap, category distribution."""
from fastapi import APIRouter
from database import get_db
from config import INITIAL_CAPITAL

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
def portfolio_analysis():
    db = get_db()

    # Total exposure per category
    categories = db.execute("""
        SELECT w.category, COUNT(*) as cnt,
               COALESCE(SUM(p.total_value), COUNT(*)*:cap) as total_value,
               COALESCE(SUM(p.pnl), 0) as total_pnl
        FROM wallets w
        LEFT JOIN (SELECT wallet_id, total_value, pnl FROM pnl_snapshots
                   WHERE id IN (SELECT MAX(id) FROM pnl_snapshots GROUP BY wallet_id)) p
          ON w.id = p.wallet_id
        WHERE w.active = 1
        GROUP BY w.category
    """, {"cap": INITIAL_CAPITAL}).fetchall()

    cat_breakdown = []
    for c in categories:
        cat_breakdown.append({
            "category": c["category"],
            "wallet_count": c["cnt"],
            "total_value": round(c["total_value"] or 0, 2),
            "total_pnl": round(c["total_pnl"] or 0, 2),
            "allocation_pct": round(c["cnt"] * 100.0 / max(1, sum(r["cnt"] for r in categories)), 1)
        })

    # Market overlap: same slug traded by multiple wallets
    overlap = db.execute("""
        SELECT t.slug, COUNT(DISTINCT t.wallet_id) as wallet_count,
               GROUP_CONCAT(DISTINCT w.name) as wallets
        FROM trade_log t
        JOIN wallets w ON t.wallet_id = w.id
        WHERE t.status = 'FILLED'
        GROUP BY t.slug
        HAVING wallet_count >= 2
        ORDER BY wallet_count DESC
        LIMIT 20
    """).fetchall()

    # Top-performing wallets
    top = db.execute("""
        SELECT w.name, w.category, p.total_value, p.pnl, p.pnl_pct
        FROM wallets w
        JOIN (SELECT wallet_id, total_value, pnl, pnl_pct FROM pnl_snapshots
              WHERE id IN (SELECT MAX(id) FROM pnl_snapshots GROUP BY wallet_id)) p
          ON w.id = p.wallet_id
        WHERE w.active = 1
        ORDER BY p.pnl_pct DESC
        LIMIT 5
    """).fetchall()

    return {
        "category_breakdown": cat_breakdown,
        "market_overlap": [dict(r) for r in overlap],
        "top_performers": [dict(r) for r in top],
        "total_value": round(sum(c["total_value"] for c in cat_breakdown), 2),
        "total_pnl": round(sum(c["total_pnl"] for c in cat_breakdown), 2),
    }
