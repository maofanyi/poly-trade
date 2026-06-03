"""Wallet CRUD API."""
from fastapi import APIRouter, HTTPException
from database import get_db
from models import WalletCreate
from trader import ensure_account
from config import INITIAL_CAPITAL

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

def _row_to_out(row, pnl_row=None) -> dict:
    return {
        "id": row["id"], "address": row["address"], "name": row["name"],
        "category": row["category"], "active": bool(row["active"]),
        "paused": bool(row["paused"]) if "paused" in row.keys() else False,
        "created_at": row["created_at"],
        "cash": pnl_row["cash"] if pnl_row else INITIAL_CAPITAL,
        "total_value": pnl_row["total_value"] if pnl_row else INITIAL_CAPITAL,
        "pnl": pnl_row["pnl"] if pnl_row else 0.0,
        "pnl_pct": pnl_row["pnl_pct"] if pnl_row else 0.0,
    }

@router.get("")
def list_wallets():
    db = get_db()
    rows = db.execute("SELECT * FROM wallets ORDER BY active DESC, name").fetchall()
    result = []
    for r in rows:
        pnl = db.execute(
            "SELECT * FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
            (r["id"],)
        ).fetchone()
        result.append(_row_to_out(r, pnl))
    return result

@router.post("")
def add_wallet(data: WalletCreate):
    db = get_db()
    existing = db.execute("SELECT id FROM wallets WHERE address = ?", (data.address,)).fetchone()
    if existing:
        # Reactivate if soft-deleted
        db.execute("UPDATE wallets SET active = 1 WHERE id = ?", (existing["id"],))
        db.commit()
        return {"ok": True, "id": existing["id"], "reactivated": True}

    db.execute(
        "INSERT INTO wallets (address, name, category) VALUES (?, ?, ?)",
        (data.address, data.name, data.category)
    )
    db.commit()
    wallet_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Initialize pm-trader account
    ensure_account(f"copy-{data.name}")

    return {"ok": True, "id": wallet_id, "reactivated": False}

@router.delete("/{wallet_id}")
def remove_wallet(wallet_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM wallets WHERE id = ?", (wallet_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Wallet not found")
    db.execute("UPDATE wallets SET active = 0 WHERE id = ?", (wallet_id,))
    db.commit()
    return {"ok": True, "name": row["name"]}

@router.post("/{wallet_id}/pause")
def pause_wallet(wallet_id: int):
    db = get_db()
    db.execute("UPDATE wallets SET paused = 1 WHERE id = ?", (wallet_id,))
    db.commit()
    return {"ok": True}

@router.post("/{wallet_id}/resume")
def resume_wallet(wallet_id: int):
    db = get_db()
    db.execute("UPDATE wallets SET paused = 0 WHERE id = ?", (wallet_id,))
    db.commit()
    return {"ok": True}

@router.get("/{wallet_id}/pnl")
def get_wallet_pnl_history(wallet_id: int, days: int = 7):
    db = get_db()
    rows = db.execute("""
        SELECT * FROM pnl_snapshots
        WHERE wallet_id = ? AND timestamp >= datetime('now', 'localtime', ?)
        ORDER BY timestamp ASC
    """, (wallet_id, f'-{days} days')).fetchall()
    return [dict(r) for r in rows]

@router.post("/validate")
def validate_wallet(data: dict):
    """Validate a Polymarket wallet address — check if it has trading history."""
    import urllib.request, json
    addr = (data.get("address") or "").strip()
    if not addr or len(addr) < 10:
        raise HTTPException(status_code=400, detail="Invalid address format")

    # Check if already in DB
    db = get_db()
    existing = db.execute("SELECT * FROM wallets WHERE address = ?", (addr,)).fetchone()
    if existing:
        return {
            "valid": True,
            "address": addr,
            "name": existing["name"],
            "category": existing["category"],
            "trades_found": None,
            "already_added": True
        }

    # Query Polymarket Data API
    try:
        url = f"https://data-api.polymarket.com/trades?user={addr}&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            trades = json.loads(resp.read().decode())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data API error: {e}")

    if not trades or len(trades) == 0:
        return {"valid": False, "address": addr, "message": "No trades found for this address"}

    # Extract info from trades
    categories = set()
    for t in trades:
        title = (t.get("title") or "").lower()
        if any(w in title for w in ["weather","temperature","rain","snow","wind","storm","hurricane"]):
            categories.add("Weather")
        elif any(w in title for w in ["election","trump","biden","senate","congress","president","political"]):
            categories.add("Politics")
        elif any(w in title for w in ["nba","nfl","mlb","ufc","soccer","football","tennis","sports"]):
            categories.add("Sports")
        elif any(w in title for w in ["ai","tech","apple","google","bitcoin","crypto"]):
            categories.add("Tech")
        else:
            categories.add("General")

    cat = list(categories)[0] if categories else "General"

    # Auto-generate name from address
    short_name = f"Wallet-{addr[:6]}"

    return {
        "valid": True,
        "address": addr,
        "name": short_name,
        "category": cat,
        "trades_found": len(trades),
        "already_added": False
    }
@router.post("/reset")
def reset_wallets_to_defaults():
    """Reset all wallets to the default 10. Deactivates custom wallets, reactivates defaults."""
    from config import DEFAULT_WALLETS
    db = get_db()
    # Soft-delete all wallets
    db.execute("UPDATE wallets SET active = 0, paused = 0")
    # Re-insert defaults (reactivate if exists, insert if new)
    for w in DEFAULT_WALLETS:
        existing = db.execute("SELECT id FROM wallets WHERE address = ?", (w["address"],)).fetchone()
        if existing:
            db.execute("UPDATE wallets SET active = 1, paused = 0, name = ?, category = ? WHERE id = ?",
                       (w["name"], w["category"], existing["id"]))
        else:
            db.execute("INSERT INTO wallets (address, name, category) VALUES (?, ?, ?)",
                       (w["address"], w["name"], w["category"]))
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM wallets WHERE active = 1").fetchone()[0]
    return {"ok": True, "active_wallets": count, "message": f"Reset to {count} default wallets"}

@router.get("/{wallet_id}/positions")
def get_wallet_positions(wallet_id: int):
    """Get current open positions with unrealized P&L."""
    import urllib.request, json as _json
    db = get_db()
    wallet = db.execute("SELECT name FROM wallets WHERE id = ?", (wallet_id,)).fetchone()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    acct = f"copy-{wallet['name']}"
    from trader import get_portfolio, get_midpoint
    positions = get_portfolio(acct)
    result = []
    for pos in (positions or []):
        slug = pos.get('slug', '')
        outcome = pos.get('outcome', '')
        shares = pos.get('shares', 0)
        if shares <= 0: continue

        # Cost basis: AVG fill_price from our BUY trades, fallback to whale_price
        cost_row = db.execute("""
            SELECT AVG(fill_price) as avg_cost, AVG(whale_price) as avg_whale FROM trade_log
            WHERE wallet_id=? AND slug=? AND LOWER(outcome)=LOWER(?) AND side='BUY' AND status='FILLED'
        """, (wallet_id, slug, outcome)).fetchone()
        cost_basis = 0.0
        if cost_row:
            cost_basis = round(cost_row['avg_cost'] or cost_row['avg_whale'] or 0, 4)

        # Live price: try pm-trader first, then Data API, then last trade price
        live_price = None
        mid = get_midpoint(slug)
        if mid:
            for k, v in mid.items():
                if k.lower() == outcome.lower() and v is not None:
                    live_price = v
                    break

        # Fallback: Data API price endpoint
        if live_price is None:
            try:
                url = f"https://data-api.polymarket.com/price?slug={urllib.parse.quote(slug)}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    prices = _json.loads(resp.read())
                if isinstance(prices, dict):
                    for k, v in prices.items():
                        if k.lower() == outcome.lower() and v is not None:
                            live_price = float(v)
                            break
            except Exception:
                pass

        # Last resort: use cost_basis as estimated current price (no P&L but shows value)
        if live_price is None and cost_basis > 0:
            live_price = cost_basis

        # Skip only if we have absolutely no data
        if live_price is None and cost_basis == 0:
            continue

        unrealized = round((live_price - cost_basis) * shares, 4) if live_price is not None and cost_basis else None
        pos_value = round(shares * (live_price or cost_basis or 0), 2)
        result.append({"slug":slug,"outcome":outcome,"shares":round(shares,4),
                       "cost_basis":cost_basis,"live_price":live_price,
                       "unrealized_pnl":unrealized,
                       "value":pos_value,
                       "active":live_price is not None and live_price != cost_basis})
    return result

@router.post("/cleanup-positions")
def cleanup_stale_positions():
    """Reset all copy-trading accounts to clear stale/expired positions, then re-init."""
    from trader import pm, INITIAL_CAPITAL
    db = get_db()
    wallets = db.execute("SELECT name FROM wallets WHERE active = 1").fetchall()
    cleaned = 0
    for w in wallets:
        acct = f"copy-{w['name']}"
        r = pm(f"pm-trader --account {acct} reset --confirm")
        if r and r.get('ok'):
            pm(f"pm-trader --account {acct} init --balance {INITIAL_CAPITAL}")
            cleaned += 1
            print(f"  Reset: {acct} -> ${INITIAL_CAPITAL}")
    return {"ok": True, "cleaned": cleaned, "message": f"Reset {cleaned} accounts to ${INITIAL_CAPITAL}"}

from scores import get_wallet_scores, refresh_all_scores

@router.get("/scores")
def list_scores():
    """Get all wallet scores sorted by copy-trading potential."""
    return get_wallet_scores()

@router.post("/scores/refresh")
def refresh_scores():
    """Force-refresh all wallet scores from Polymarket Data API."""
    updated = refresh_all_scores()
    return {"ok": True, "updated": updated}

from scores import discover_wallets, get_discovered_wallets

@router.get("/discovered")
def list_discovered():
    """Get auto-discovered high-performing wallets."""
    return get_discovered_wallets()

@router.post("/discovered/scan")
def scan_discovered():
    """Run wallet discovery scan now."""
    found = discover_wallets()
    return {"ok": True, "found": len(found), "wallets": found}
