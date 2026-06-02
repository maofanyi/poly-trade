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

    # Score formula: weighted sum of diversity, volume, and consistency
    market_score = min(unique_markets / 30, 1) * 35      # Diverse = more market knowledge
    volume_score = min(total_vol / 20000, 1) * 25        # High volume = conviction
    size_score = min((total_vol / max(n, 1)) / 200, 1) * 20  # Larger avg trade = not a bot
    buy_pct = buy_count / n if n > 0 else 0
    balance_penalty = 1.0 - abs(buy_pct - 0.5) * 0.3     # Balanced = not directional bias
    consistency_score = min(n / 50, 1) * 20                # More trades in sample = consistent
    score = round((market_score + volume_score + size_score + consistency_score) * balance_penalty, 1)

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


def discover_wallets(max_discover: int = 10) -> list[dict]:
    """Discover new high-performing wallets from active markets.

    1. Get active market slugs from monitored wallets' recent trades
    2. For each market, find other traders
    3. Score new traders, return top candidates
    """
    db = get_db()

    # Collect known addresses (monitored + already discovered)
    known = set()
    for row in db.execute("SELECT address FROM wallets").fetchall():
        known.add(row['address'].lower())
    for row in db.execute("SELECT address FROM discovered_wallets").fetchall():
        known.add(row['address'].lower())

    # Get active market slugs from monitored wallets' recent trades
    market_slugs = set()
    active_wallets = db.execute("SELECT address FROM wallets WHERE active = 1").fetchall()
    for w in active_wallets:
        try:
            trades = _fetch(f"{DATA_API}/trades?user={w['address']}&limit=10")
            time.sleep(0.2)
            for t in (trades or [])[:3]:
                slug = t.get('slug', '')
                if slug:
                    market_slugs.add(slug)
        except Exception:
            continue

    if not market_slugs:
        print("  No active markets found for discovery")
        return []

    print(f"  Scanning {len(market_slugs)} markets for new traders...")

    # For each market, find other traders
    candidates = {}  # address -> {trade_count, total_vol}
    for slug in list(market_slugs)[:8]:  # Limit to 8 markets
        try:
            market_trades = _fetch(f"{DATA_API}/trades?market={slug}&limit=30")
            time.sleep(0.3)
            for t in (market_trades or []):
                addr = (t.get('user') or t.get('maker') or '').lower()
                if not addr or addr in known:
                    continue
                if addr not in candidates:
                    candidates[addr] = {'trades': 0, 'volume': 0.0}
                candidates[addr]['trades'] += 1
                candidates[addr]['volume'] += float(t.get('size', 0)) * float(t.get('price', 0.5))
        except Exception as e:
            continue

    if not candidates:
        print("  No new traders discovered")
        return []

    # Filter: require at least 3 trades in our sample
    candidates = {a: c for a, c in candidates.items() if c['trades'] >= 3}
    print(f"  Found {len(candidates)} potential new wallets (≥3 trades)")

    # Score top candidates
    scored = []
    for addr in list(candidates.keys())[:30]:  # Score at most 30
        result = score_wallet(addr)
        if result and result['score'] > 30:
            # Try to determine category from trade titles
            cat = "General"
            try:
                sample = _fetch(f"{DATA_API}/trades?user={addr}&limit=3")
                titles = ' '.join(t.get('title', '') for t in (sample or [])).lower()
                if any(w in titles for w in ['temperature', 'weather', 'rain', 'snow', 'storm']):
                    cat = 'Weather'
                elif any(w in titles for w in ['election', 'trump', 'senate', 'president', 'political']):
                    cat = 'Politics'
                elif any(w in titles for w in ['nba', 'nfl', 'mlb', 'ufc', 'soccer', 'tennis']):
                    cat = 'Sports'
                time.sleep(0.2)
            except Exception:
                pass

            # Generate name
            short_name = f"发现-{addr[:6]}"

            scored.append({
                'address': addr,
                'name': short_name,
                'category': cat,
                'trades': result['trades'],
                'volume': result['volume'],
                'markets': result['markets'],
                'score': result['score'],
            })
            print(f"    {short_name}: score={result['score']:.0f} {result['trades']}trades")

    # Sort by score desc, take top N
    scored.sort(key=lambda x: x['score'], reverse=True)
    top = scored[:max_discover]

    # Save to discovered_wallets table
    for w in top:
        db.execute("""
            INSERT OR REPLACE INTO discovered_wallets (address, name, category, trades, volume, markets, score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        """, (w['address'], w['name'], w['category'], w['trades'], w['volume'], w['markets'], w['score']))
    db.commit()

    print(f"  Discovered {len(top)} new wallets")
    return top


def get_discovered_wallets() -> list[dict]:
    """Get all discovered wallets, sorted by score desc."""
    db = get_db()
    rows = db.execute("""
        SELECT * FROM discovered_wallets
        ORDER BY score DESC
    """).fetchall()
    return [dict(r) for r in rows]


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
