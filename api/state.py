"""Full state snapshot API + health check."""
import urllib.request, urllib.parse
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
    traded_list = []
    total_cash = 0.0
    total_value = 0.0

    for w in wallets:
        pnl = db.execute(
            "SELECT * FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
            (w["id"],)
        ).fetchone()
        if pnl:
            wallet_list.append({
                "id": w["id"], "address": w["address"], "name": w["name"],
                "category": w["category"], "active": bool(w["active"]),
                "created_at": w["created_at"],
                "cash": pnl["cash"], "total_value": pnl["total_value"],
                "pnl": pnl["pnl"], "pnl_pct": pnl["pnl_pct"],
            })
            total_cash += pnl["cash"] or 0
            total_value += pnl["total_value"] or 0
            traded_list.append(w["name"])
        else:
            # Wallet hasn't traded yet — return with null P&L, frontend filters it
            wallet_list.append({
                "id": w["id"], "address": w["address"], "name": w["name"],
                "category": w["category"], "active": bool(w["active"]),
                "created_at": w["created_at"],
                "cash": None, "total_value": None,
                "pnl": None, "pnl_pct": None,
            })

    wallet_count = len(traded_list)
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
    import os
    db = get_db()
    wallet_count = db.execute("SELECT COUNT(*) FROM wallets WHERE active = 1").fetchone()[0]
    db_path = os.environ.get("DB_PATH", "data/trade.db")
    db_exists = os.path.exists(db_path)
    return {
        "status": "ok",
        "wallets": wallet_count,
        "db_persisted": db_exists
    }

@router.get("/market/{slug:path}/trades")
def get_market_trades(slug: str, limit: int = 50):
    """Get price history for chart — local accumulated data + Data API recent trades."""
    import json as _json
    from datetime import datetime
    seen = set()
    points = []

    # 1. Local price_history (accumulated since our first trade — days/weeks of data)
    db = get_db()
    local = db.execute("""
        SELECT slug, outcome, price, recorded_at FROM price_history
        WHERE slug = ? ORDER BY recorded_at ASC
    """, (slug,)).fetchall()
    for r in local:
        try:
            ts = int(datetime.fromisoformat(r['recorded_at']).timestamp())
        except Exception:
            continue
        k = f'{ts}_{r[\"price\"]:.4f}'
        if k in seen: continue
        seen.add(k)
        points.append({"t": ts, "p": round(r['price'], 4), "o": r['outcome']})

    # 2. Our trade_log entries for this market (BUY/SELL execution prices)
    trades = db.execute("""
        SELECT whale_price as price, side, outcome, timestamp FROM trade_log
        WHERE slug = ? AND status IN ('FILLED','SKIPPED') ORDER BY id ASC
    """, (slug,)).fetchall()
    for t in trades:
        try:
            ts = int(datetime.fromisoformat(t['timestamp']).timestamp())
        except Exception:
            continue
        k = f'{ts}_{t[\"price\"]:.4f}'
        if k in seen: continue
        seen.add(k)
        points.append({"t": ts, "p": round(float(t['price']), 4), "o": t['outcome'] or 'Yes'})

    # 3. Data API recent trades (latest ~50 trades for freshness)
    try:
        for offset in [0, 50]:
            url = f"https://data-api.polymarket.com/trades?slug={urllib.parse.quote(slug)}&limit=50&offset={offset}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                api_trades = _json.loads(resp.read())
            for t in (api_trades or []):
                ts = int(t.get('timestamp', 0))
                k = f'{ts}_{float(t.get(\"price\",0)):.4f}'
                if k in seen: continue
                seen.add(k)
                points.append({"t": ts, "p": float(t.get('price', 0)), "o": t.get('outcome', '')})
    except Exception:
        pass

    points.sort(key=lambda x: x['t'])
    return {"slug": slug, "points": points}
