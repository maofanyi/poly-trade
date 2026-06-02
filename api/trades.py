"""Trades listing API."""
from fastapi import APIRouter, Query
from database import get_db

router = APIRouter(prefix="/api/trades", tags=["trades"])

@router.get("")
def list_trades(
    wallet_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    db = get_db()
    conditions = []
    params = {}

    if wallet_id is not None:
        conditions.append("t.wallet_id = :wallet_id")
        params["wallet_id"] = wallet_id
    if status is not None:
        conditions.append("t.status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params["limit"] = limit
    params["offset"] = offset

    rows = db.execute(f"""
        SELECT t.*, w.name as wallet_name
        FROM trade_log t JOIN wallets w ON t.wallet_id = w.id
        {where}
        ORDER BY t.id DESC
        LIMIT :limit OFFSET :offset
    """, params).fetchall()

    # Count total (same filter, no limit/offset)
    count_params = {k: v for k, v in params.items() if k not in ('limit', 'offset')}
    count_where = where
    count_sql = f"SELECT COUNT(*) FROM trade_log t {count_where}"
    total = db.execute(count_sql, count_params).fetchone()[0]

    return {
        "trades": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset
    }
