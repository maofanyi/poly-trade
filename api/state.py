"""Full state snapshot API + health check."""
from fastapi import APIRouter
from database import get_db
from config import INITIAL_CAPITAL
from models import AlertConfigUpdate
from alerts import update_config as alerts_update_config

router = APIRouter(prefix="/api", tags=["state"])

@router.get("/state")
def get_state():
    db = get_db()

    wallets = db.execute("SELECT * FROM wallets WHERE active = 1 ORDER BY name").fetchall()
    wallet_list = []
    total_cash = 0.0
    total_value = 0.0

    for w in wallets:
        pnl = db.execute(
            "SELECT * FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
            (w["id"],)
        ).fetchone()
        wallet_list.append({
            "id": w["id"], "address": w["address"], "name": w["name"],
            "category": w["category"], "active": bool(w["active"]),
            "created_at": w["created_at"],
            "cash": pnl["cash"] if pnl else None,
            "total_value": pnl["total_value"] if pnl else None,
            "pnl": pnl["pnl"] if pnl else None,
            "pnl_pct": pnl["pnl_pct"] if pnl else None,
        })
        if pnl:
            total_cash += pnl["cash"] or 0
            total_value += pnl["total_value"] or 0

    wallet_count = len(wallet_list)
    total_capital = INITIAL_CAPITAL * wallet_count
    total_pnl = round(total_value - total_capital, 2)
    total_pnl_pct = round(total_pnl / total_capital * 100, 2) if total_capital > 0 else 0.0

    trades = db.execute("""
        SELECT t.*, w.name as wallet_name
        FROM trade_log t JOIN wallets w ON t.wallet_id = w.id
        ORDER BY t.id DESC LIMIT 100
    """).fetchall()

    last_scan = db.execute("SELECT scan_end FROM scan_log ORDER BY id DESC LIMIT 1").fetchone()
    total_trades = db.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]

    return {
        "wallets": wallet_list,
        "trades": [dict(t) for t in trades],
        "summary": {
            "total_capital": total_capital,
            "total_cash": round(total_cash, 2),
            "total_value": round(total_value, 2),
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "wallet_count": wallet_count,
            "active_wallet_count": wallet_count,
            "last_scan": last_scan["scan_end"] if last_scan else None,
            "total_trades": total_trades,
            "win_rate": None
        },
        "last_scan": last_scan["scan_end"] if last_scan else None
    }

@router.get("/alerts")
def get_alert_config():
    db = get_db()
    row = db.execute("SELECT * FROM alert_config WHERE id = 1").fetchone()
    if not row:
        db.execute("INSERT INTO alert_config (id) VALUES (1)")
        db.commit()
        return {"enabled": 1, "pnl_threshold_pct": -20.0, "single_loss_usd": 10.0, "webhook_type": None, "webhook_url": None}
    return dict(row)

@router.put("/alerts")
def update_alert_config(data: AlertConfigUpdate):
    db = get_db()
    alerts_update_config(db, **{k: v for k, v in data.model_dump().items() if v is not None})
    return {"ok": True}

@router.get("/health")
def health():
    return {"status": "ok"}
