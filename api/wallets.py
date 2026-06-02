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
