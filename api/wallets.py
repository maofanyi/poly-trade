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
