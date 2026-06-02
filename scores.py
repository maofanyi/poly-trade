"""Wallet performance scoring — analyzes candidate wallets from Polymarket Data API."""
import json
import time
import urllib.request
from database import get_db

DATA_API = "https://data-api.polymarket.com"


def _fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def score_wallet(address: str) -> dict | None:
    """Fetch recent trades for a wallet and compute copy-trading score."""
    try:
        trades = _fetch(f"{DATA_API}/trades?user={address}&limit=50")
        time.sleep(0.3)  # Rate limit
    except Exception:
        return None

    if not trades:
        return {"trades": 0, "volume": 0, "markets": 0, "buy_pct": 0, "score": 0}

    n = len(trades)
    buy_count = sum(1 for t in trades if t.get('side') == 'BUY')
    unique_markets = len(set(t.get('conditionId', '') for t in trades))
    total_vol = sum(float(t.get('size', 0)) * float(t.get('price', 0.5)) for t in trades)

    freq_score = min(n, 50) / 50 * 30
    div_score = min(unique_markets, 20) / 20 * 25
    vol_score = min(total_vol / 5000, 1) * 25
    buy_pct = buy_count / n if n > 0 else 0
    balance_penalty = 1.0 - abs(buy_pct - 0.5) * 0.5
    score = round((freq_score + div_score + vol_score) * balance_penalty, 1)

    return {
        "trades": n,
        "volume": round(total_vol, 1),
        "markets": unique_markets,
        "buy_pct": round(buy_pct, 2),
        "score": score,
        "updated_at": __import__('datetime').datetime.now().isoformat()
    }


def refresh_all_scores():
    """Refresh scores for all candidate wallets in the DB."""
    db = get_db()
    wallets = db.execute("SELECT id, address, name FROM wallets WHERE active = 1").fetchall()
    updated = 0
    for w in wallets:
        result = score_wallet(w['address'])
        if result is None:
            continue
        db.execute("""
            INSERT OR REPLACE INTO wallet_scores (wallet_id, trades, volume, markets, buy_pct, score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        """, (w['id'], result['trades'], result['volume'], result['markets'],
              result['buy_pct'], result['score']))
        updated += 1
        print(f"  Scored {w['name']}: {result['score']} ({result['trades']} trades, {result['markets']} markets)")
    db.commit()
    print(f"  Scores refreshed: {updated} wallets")
    return updated


def get_wallet_scores() -> list[dict]:
    """Get all wallet scores with names, sorted by score desc."""
    db = get_db()
    rows = db.execute("""
        SELECT w.name, w.address, w.category, s.trades, s.volume, s.markets,
               s.buy_pct, s.score, s.updated_at
        FROM wallets w
        LEFT JOIN wallet_scores s ON w.id = s.wallet_id
        WHERE w.active = 1
        ORDER BY s.score DESC
    """).fetchall()
    return [dict(r) for r in rows]
