"""Trade scanning loop — fetches trades, executes via pm-trader, persists to DB."""
import json
import time
import urllib.request
from datetime import datetime
from config import (DATA_API, INITIAL_CAPITAL, MAX_TRADES_PER_SCAN, SCAN_INTERVAL,
                    MIN_TRADE_USD, MAX_PER_MARKET_USD, MAX_OPEN_POSITIONS,
                    PRICE_DEVIATION_LIMIT, DAILY_LOSS_LIMIT, COPY_RATIO,
                    GLOBAL_LOSS_THRESHOLD)
from database import get_db
import re
from trader import ensure_account, place_market_order, get_portfolio, get_midpoint

# Deferred import to avoid circular dependency
_ws_manager = None

def set_ws_manager(mgr):
    global _ws_manager
    _ws_manager = mgr

def api_fetch(url: str) -> list:
    """Fetch JSON from Polymarket Data API."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def get_wallet_id(db, name: str) -> int | None:
    row = db.execute("SELECT id FROM wallets WHERE name = ? AND active = 1", (name,)).fetchone()
    return row['id'] if row else None

def is_txn_seen(db, txn_hash: str) -> bool:
    row = db.execute("SELECT id FROM trade_log WHERE txn_hash = ?", (txn_hash,)).fetchone()
    return row is not None

def log_trade(db, wallet_id: int, **fields):
    fields.setdefault("skip_reason", None)
    db.execute("""
        INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd,
                               fill_price, status, slippage, pnl_realized, slug, outcome, timestamp, skip_reason)
        VALUES (:wallet_id, :txn_hash, :side, :size, :whale_price, :sim_usd,
                :fill_price, :status, :slippage, :pnl_realized, :slug, :outcome, :timestamp, :skip_reason)
    """, dict(wallet_id=wallet_id, **fields))
    db.commit()

def get_cost_basis(db, wallet_id: int, slug: str) -> tuple[float, float]:
    """Return (avg_cost_per_share, total_shares) for last BUY of this slug."""
    row = db.execute("""
        SELECT fill_price, size FROM trade_log
        WHERE wallet_id = ? AND slug = ? AND side = 'BUY' AND status = 'FILLED'
        ORDER BY id DESC LIMIT 1
    """, (wallet_id, slug)).fetchone()
    if row and row['fill_price']:
        return (row['fill_price'], row['size'] or 0)
    return (0, 0)

def update_position(db, wallet_id: int, trade: dict):
    """Accumulate whale position from a single trade."""
    slug = trade.get('slug', '')
    outcome = trade.get('outcome', '')
    side = (trade.get('side', 'BUY') or 'BUY').upper()
    size = float(trade.get('size', 0))
    ts = str(trade.get('timestamp', ''))

    if not slug or not outcome or size <= 0:
        return

    row = db.execute(
        "SELECT whale_shares FROM positions WHERE wallet_id = ? AND slug = ? AND outcome = ?",
        (wallet_id, slug, outcome)
    ).fetchone()

    current = row['whale_shares'] if row else 0.0

    if side == 'BUY':
        new_whale = current + size
    else:
        new_whale = max(0.0, current - size)

    db.execute("""
        INSERT INTO positions (wallet_id, slug, outcome, whale_shares, last_trade_ts)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(wallet_id, slug, outcome) DO UPDATE SET
            whale_shares = excluded.whale_shares,
            last_trade_ts = excluded.last_trade_ts,
            updated_at = datetime('now','localtime')
    """, (wallet_id, slug, outcome, new_whale, ts))
    db.commit()


def get_whale_positions(db, wallet_id: int) -> list:
    """Return all current whale positions for a wallet (shares > 0)."""
    rows = db.execute(
        "SELECT slug, outcome, whale_shares FROM positions WHERE wallet_id = ? AND whale_shares > 0",
        (wallet_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def risk_check(db, wallet_name: str, slug: str, side: str, amount: float,
               whale_price: float, outcome: str = 'Yes') -> tuple:
    """Return (passed: bool, skip_reason: str)."""
    if amount < MIN_TRADE_USD:
        return False, 'size_too_small'

    # Check open positions count
    portfolio = get_portfolio(f"copy-{wallet_name}")
    if len(portfolio) >= MAX_OPEN_POSITIONS and side == 'BUY':
        return False, 'max_positions'

    # Check per-market cap via portfolio
    mid = get_midpoint(slug)
    current_price = 0.5
    if mid:
        current_price = mid.get('YES', mid.get('yes', 0.5))

    existing_usd = 0.0
    for p in portfolio:
        if p.get('slug') == slug:
            existing_usd += p.get('shares', 0) * current_price
    if side == 'BUY' and existing_usd + amount > MAX_PER_MARKET_USD:
        return False, 'per_market_cap'

    # Price deviation check
    if mid and whale_price > 0:
        deviation = abs(current_price - whale_price) / whale_price
        if deviation > PRICE_DEVIATION_LIMIT:
            return False, 'price_gap'

    # Daily loss check
    wallet_row = db.execute(
        "SELECT id FROM wallets WHERE name = ?", (wallet_name,)
    ).fetchone()
    if wallet_row:
        today = datetime.now().strftime('%Y-%m-%d')
        row = db.execute(
            "SELECT COALESCE(SUM(pnl_realized), 0) as daily_loss FROM trade_log "
            "WHERE wallet_id = ? AND pnl_realized < 0 AND timestamp >= ?",
            (wallet_row['id'], today)
        ).fetchone()
        if row and abs(row['daily_loss']) > DAILY_LOSS_LIMIT:
            return False, 'daily_limit'

    return True, ''


def compute_diffs(db, wallet_id: int, wallet_name: str) -> list:
    """Compare whale positions vs our positions, return list of trade actions."""
    whale_positions = get_whale_positions(db, wallet_id)
    our_positions = get_portfolio(f"copy-{wallet_name}")

    # Index our positions by slug|outcome
    ours = {}
    for p in our_positions:
        key = f"{p['slug']}|{p['outcome']}"
        ours[key] = p

    actions = []

    # Whale positions -> check what we should hold
    for wp in whale_positions:
        key = f"{wp['slug']}|{wp['outcome']}"
        our_shares = ours.get(key, {}).get('shares', 0)

        if wp['whale_shares'] > 0 and our_shares == 0:
            # New position: BUY proportional amount
            mid = get_midpoint(wp['slug'])
            est_price = 0.5
            if mid:
                est_price = mid.get('YES', mid.get('yes', 0.5))
            whale_notional = wp['whale_shares'] * est_price
            amount = min(max(whale_notional * COPY_RATIO, 1.0), MAX_PER_MARKET_USD)
            actions.append({
                'slug': wp['slug'], 'outcome': wp['outcome'],
                'action': 'BUY', 'amount': round(amount, 2)
            })
        elif wp['whale_shares'] == 0 and our_shares > 0:
            actions.append({
                'slug': wp['slug'], 'outcome': wp['outcome'],
                'action': 'SELL', 'amount': our_shares
            })

    # We hold positions that whale doesn't -> SELL
    for key, op in ours.items():
        slug, outcome = key.split('|', 1)
        whale_has = any(
            wp['slug'] == slug and wp['outcome'] == outcome
            for wp in whale_positions
        )
        if not whale_has and op.get('shares', 0) > 0:
            actions.append({
                'slug': slug, 'outcome': outcome,
                'action': 'SELL', 'amount': op['shares']
            })

    return actions


def _resolve_expired_positions(acct_name: str) -> float:
    """Query Gamma API to resolve expired positions. Returns adjustment to total_value."""
    import json as _json
    from trader import get_portfolio
    positions = get_portfolio(acct_name)
    if not positions:
        return 0.0

    now_ts = int(time.time())
    adjustment = 0.0

    for pos in positions:
        slug = pos.get('slug', '')
        outcome = pos.get('outcome', '')
        shares = pos.get('shares', 0)
        if not slug or shares <= 0:
            continue

        # Check if market has expired
        expiry = _extract_expiry(slug)
        if not expiry or (now_ts - expiry) <= 3600:
            continue

        # Query Gamma API for resolution
        try:
            url = f"https://gamma-api.polymarket.com/events?slug={slug}"
            req = __import__('urllib.request').Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with __import__('urllib.request').urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            if not data:
                continue
            markets_raw = data[0].get('markets', [])
            if isinstance(markets_raw, str):
                try: markets_raw = _json.loads(markets_raw)
                except: continue
            for m in markets_raw:
                outcomes = m.get('outcomes', [])
                prices = m.get('outcomePrices', [])
                if isinstance(outcomes, str):
                    try: outcomes = _json.loads(outcomes)
                    except: outcomes = []
                if isinstance(prices, str):
                    try: prices = _json.loads(prices)
                    except: prices = []
                winner = None
                for o, p in zip(outcomes, prices):
                    try: pf = float(p)
                    except: pf = 0
                    if pf >= 0.99:
                        winner = o
                        break
                if winner and outcome.lower() == winner.lower():
                    adjustment += shares * 1.0  # Won: each share worth $1
                    print(f"    ✓ {slug[:30]} {outcome} resolved WIN +${shares:.2f}")
                else:
                    print(f"    ✗ {slug[:30]} {outcome} resolved LOSE ({winner} won)")
                break
        except Exception as e:
            print(f"    ? {slug[:30]} resolution error: {e}")
            continue

    return round(adjustment, 2)


def snapshot_pnl(db, wallet_id: int, acct_name: str):
    """Take a P&L snapshot for one wallet, including resolved positions."""
    bal = ensure_account(acct_name)
    cash_val = round(bal['cash'], 2)
    pm_total = round(bal['total_value'], 2)

    # Resolve expired positions using Gamma API
    resolution_adjustment = _resolve_expired_positions(acct_name)

    # Total value = pm-trader value + resolved position adjustments
    # (pm-trader may show stale prices for expired markets; we fix that)
    total_val = round(pm_total + resolution_adjustment, 2)
    pnl_val = round(total_val - INITIAL_CAPITAL, 2)
    pnl_pct = round(pnl_val / INITIAL_CAPITAL * 100, 2)
    db.execute("""
        INSERT INTO pnl_snapshots (wallet_id, cash, total_value, pnl, pnl_pct)
        VALUES (?, ?, ?, ?, ?)
    """, (wallet_id, cash_val, total_val, pnl_val, pnl_pct))
    db.commit()

    # Record price history for charting (dedup: skip if price unchanged)
    from trader import get_portfolio, get_midpoint
    positions = get_portfolio(acct_name) or []
    for pos in positions:
        slug = pos.get('slug', '')
        outcome = pos.get('outcome', '')
        mid = get_midpoint(slug)
        if mid:
            for k, v in mid.items():
                if v is not None and k.lower() == outcome.lower():
                    price = round(v, 6)
                    last = db.execute(
                        "SELECT price FROM price_history WHERE slug=? AND outcome=? ORDER BY id DESC LIMIT 1",
                        (slug, outcome)).fetchone()
                    if last and abs(last['price'] - price) < 0.0001:
                        continue  # Price hasn't changed — skip
                    db.execute("INSERT INTO price_history (slug, outcome, price) VALUES (?,?,?)",
                               (slug, outcome, price))
    db.commit()

    # Auto-pause if loss exceeds 25%
    if pnl_pct <= -25:
        db.execute("UPDATE wallets SET paused = 1 WHERE id = ?", (wallet_id,))
        db.commit()
        print(f"    ⚠️ {acct_name} paused: loss {pnl_pct:.1f}% exceeds threshold")

def _extract_expiry(slug: str) -> int | None:
    """Try to extract market expiry timestamp from slug. Returns Unix timestamp or None."""
    # Pattern: ends with a 10-digit Unix timestamp (2020–2033 range)
    m = re.search(r'[_-](\d{10})$', slug)
    if m:
        ts = int(m.group(1))
        if 1577836800 < ts < 2000000000:  # 2020-01-01 to 2033-05-18
            return ts
    return None


def _is_market_expiring(slug: str, min_seconds: int = 3600) -> bool:
    """Check if market expires within min_seconds (default 1 hour)."""
    expiry = _extract_expiry(slug)
    if expiry is None:
        return False  # Can't determine — allow trade
    remaining = expiry - int(__import__('time').time())
    return remaining < min_seconds


def _is_market_closed(db, slug: str) -> bool:
    row = db.execute("SELECT slug FROM closed_markets WHERE slug = ?", (slug,)).fetchone()
    return row is not None


def _mark_market_closed(db, slug: str):
    db.execute("INSERT OR IGNORE INTO closed_markets (slug) VALUES (?)", (slug,))
    db.commit()


def scan_wallet_position_sync(db, wallet: dict) -> int:
    """Fetch wallet trades, update position model, compute diffs, execute."""
    wallet_id = wallet['id']
    wallet_name = wallet['name']

    # Check paused
    row = db.execute("SELECT paused FROM wallets WHERE id = ?", (wallet_id,)).fetchone()
    if row and row['paused']:
        return 0

    # Fetch recent trades (limit 50 to cover window)
    try:
        trades = api_fetch(f"{DATA_API}/trades?user={wallet['address']}&limit=50")
    except Exception as e:
        print(f"  [{wallet_name}] API error: {e}")
        return 0

    if not trades:
        return 0

    new_count = 0
    skipped_txn_hashes = set()
    for t in trades:
        txn = t.get('transactionHash', '')
        if not txn or txn in skipped_txn_hashes:
            continue
        skipped_txn_hashes.add(txn)

        # Skip if this trade is older than our last update for this position
        trade_ts = str(t.get('timestamp', ''))
        slug = t.get('slug', '')
        outcome = t.get('outcome', '')
        if slug and outcome:
            pos_row = db.execute(
                "SELECT last_trade_ts FROM positions WHERE wallet_id = ? AND slug = ? AND outcome = ?",
                (wallet_id, slug, outcome)
            ).fetchone()
            if pos_row and pos_row['last_trade_ts'] and trade_ts <= pos_row['last_trade_ts']:
                continue

        update_position(db, wallet_id, t)
        # Log to trade_log for audit
        side = (t.get('side', 'BUY') or 'BUY').upper()
        log_trade(db, wallet_id,
                  txn_hash=txn,
                  side=side,
                  size=float(t.get('size', 0)),
                  whale_price=float(t.get('price', 0.5)),
                  sim_usd=0,
                  fill_price=None,
                  status='SYNCED',
                  slippage=0,
                  pnl_realized=0,
                  slug=slug,
                  outcome=outcome,
                  timestamp=datetime.now().isoformat())
        new_count += 1

    # Always compute diffs and execute — not gated on new_count.
    # Position mirroring means we sync on every scan, even without new trades.
    actions = compute_diffs(db, wallet_id, wallet_name)
    executed = 0
    for a in actions:
        passed, reason = risk_check(db, wallet_name, a['slug'], a['action'],
                                    a['amount'], 0.5, a.get('outcome', 'Yes'))
        if not passed:
            log_trade(db, wallet_id,
                      txn_hash=f"risk_{a['slug']}_{a['outcome']}_{int(time.time())}",
                      side=a['action'], size=a['amount'], whale_price=0.5,
                      sim_usd=0, fill_price=None, status='SKIPPED',
                      slippage=0, pnl_realized=0,
                      slug=a['slug'], outcome=a['outcome'],
                      timestamp=datetime.now().isoformat(),
                      skip_reason=reason)
            continue

        side_str = 'buy' if a['action'] == 'BUY' else 'sell'
        result = place_market_order(f"copy-{wallet_name}", a['slug'], a['outcome'],
                                    side_str, a['amount'])

        if result and result.get('ok'):
            fill_data = result.get('data', {}).get('trade', {})
            log_trade(db, wallet_id,
                      txn_hash=f"sync_{a['slug']}_{a['outcome']}_{int(time.time())}",
                      side=a['action'], size=a['amount'], whale_price=0.5,
                      sim_usd=a['amount'],
                      fill_price=fill_data.get('avg_price'),
                      status='FILLED', slippage=0,
                      pnl_realized=0, slug=a['slug'], outcome=a['outcome'],
                      timestamp=datetime.now().isoformat())
            executed += 1
        else:
            err = str(result.get('error', 'no response')) if result else 'no response'
            status = 'SKIPPED' if ('not found' in err.lower() or 'MARKET_NOT_FOUND' in err) else 'FAILED'
            reason2 = 'market_not_found' if status == 'SKIPPED' else 'error'
            log_trade(db, wallet_id,
                      txn_hash=f"err_{a['slug']}_{a['outcome']}_{int(time.time())}",
                      side=a['action'], size=a['amount'], whale_price=0.5,
                      sim_usd=0, fill_price=None, status=status,
                      slippage=0, pnl_realized=0,
                      slug=a['slug'], outcome=a['outcome'],
                      timestamp=datetime.now().isoformat(),
                      skip_reason=reason2)

    if executed > 0:
        snapshot_pnl(db, wallet_id, f"copy-{wallet_name}")

    return new_count

def _check_global_loss(db):
    """Pause all wallets if total portfolio loss > GLOBAL_LOSS_THRESHOLD."""
    wallets = db.execute(
        "SELECT id, name FROM wallets WHERE active = 1 AND paused = 0"
    ).fetchall()
    total_value = 0.0
    active_count = 0
    for w in wallets:
        pnl = db.execute(
            "SELECT total_value FROM pnl_snapshots WHERE wallet_id = ? ORDER BY id DESC LIMIT 1",
            (w['id'],)
        ).fetchone()
        if pnl:
            total_value += pnl['total_value']
            active_count += 1
    if active_count > 0:
        total_capital = INITIAL_CAPITAL * active_count
        loss_pct = (total_capital - total_value) / total_capital
        if loss_pct > GLOBAL_LOSS_THRESHOLD:
            db.execute("UPDATE wallets SET paused = 1 WHERE active = 1")
            db.commit()
            print(f"  !! GLOBAL CIRCUIT BREAKER: loss {loss_pct*100:.1f}%")


def _broadcast_pnl(db, wallets):
    """Send P&L update via WebSocket."""
    pnl_data = []
    for w in wallets:
        row = db.execute(
            "SELECT * FROM pnl_snapshots WHERE wallet_id = ? ORDER BY id DESC LIMIT 1",
            (w["id"],)
        ).fetchone()
        if row:
            pnl_data.append({
                "name": w["name"], "wallet_id": w["id"],
                "cash": row["cash"], "total_value": row["total_value"],
                "pnl": row["pnl"], "pnl_pct": row["pnl_pct"]
            })
    if pnl_data:
        try:
            import asyncio as _asyncio
            _asyncio.run(_ws_manager.broadcast({"type": "pnl_update", "wallets": pnl_data}))
        except Exception:
            pass


def scan_loop():
    """Position mirroring loop — 5s interval, sync whale positions to ours."""
    db = get_db()
    scan_num = 0

    # Set started_at for wallets that have traded but don't have it set
    db.execute("""
        UPDATE wallets SET started_at = (
            SELECT MIN(timestamp) FROM trade_log
            WHERE trade_log.wallet_id = wallets.id AND status = 'FILLED'
        ) WHERE started_at IS NULL
          AND id IN (SELECT DISTINCT wallet_id FROM trade_log WHERE status = 'FILLED')
    """)
    db.execute("UPDATE wallets SET started_at = created_at WHERE started_at IS NULL")
    db.commit()

    print(f"Scanner started. Position mirroring mode. Interval: {SCAN_INTERVAL}s")

    while True:
        try:
            scan_num += 1
            scan_start = datetime.now()

            db = get_db()
            db.execute("INSERT INTO scan_log (scan_start) VALUES (?)",
                       (scan_start.isoformat(),))
            db.commit()
            scan_log_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            wallets = db.execute(
                "SELECT id, name, address, category FROM wallets WHERE active = 1"
            ).fetchall()
            total_new = 0

            for w in wallets:
                try:
                    total_new += scan_wallet_position_sync(db, dict(w))
                except Exception as e:
                    print(f"  [{w['name']}] scan error: {e}")

            scan_end = datetime.now()
            elapsed = (scan_end - scan_start).total_seconds()
            db.execute(
                "UPDATE scan_log SET scan_end=?, new_trades_found=?, status=? WHERE id=?",
                (scan_end.isoformat(), total_new, 'ok', scan_log_id)
            )
            db.commit()

            # Check global loss threshold
            _check_global_loss(db)

            # Broadcast P&L update via WebSocket
            if _ws_manager:
                _broadcast_pnl(db, wallets)

            print(f"  Scan #{scan_num} done in {elapsed:.1f}s | Updates: {total_new}")
        except Exception as e:
            import traceback
            print(f"  !! Scanner error (will retry): {e}")
            traceback.print_exc()

        time.sleep(SCAN_INTERVAL)
