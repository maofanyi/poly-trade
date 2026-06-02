"""Trade scanning loop — fetches trades, executes via pm-trader, persists to DB."""
import json
import time
import urllib.request
from datetime import datetime
from config import DATA_API, INITIAL_CAPITAL, MAX_TRADES_PER_SCAN, SCAN_INTERVAL
from database import get_db
import re
from trader import ensure_account, place_market_order, has_position, get_portfolio

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
    db.execute("""
        INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd,
                               fill_price, status, slippage, pnl_realized, slug, outcome, timestamp)
        VALUES (:wallet_id, :txn_hash, :side, :size, :whale_price, :sim_usd,
                :fill_price, :status, :slippage, :pnl_realized, :slug, :outcome, :timestamp)
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

    # Record price history for charting (from our entry point onwards)
    from trader import get_portfolio, get_midpoint
    positions = get_portfolio(acct_name) or []
    for pos in positions:
        slug = pos.get('slug', '')
        outcome = pos.get('outcome', '')
        mid = get_midpoint(slug)
        if mid:
            for k, v in mid.items():
                if v is not None and k.lower() == outcome.lower():
                    db.execute("INSERT INTO price_history (slug, outcome, price) VALUES (?,?,?)",
                               (slug, outcome, round(v, 6)))
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


def scan_wallet(db, wallet: dict, ms: int) -> int:
    """Scan one wallet for new trades. Returns count of new trades processed."""
    wallet_id = get_wallet_id(db, wallet['name'])
    if not wallet_id:
        return 0

    # Check if wallet is paused
    paused_row = db.execute("SELECT paused FROM wallets WHERE id = ?", (wallet_id,)).fetchone()
    if paused_row and paused_row['paused']:
        return 0  # Skip this wallet entirely

    try:
        trades = api_fetch(f"{DATA_API}/trades?user={wallet['address']}&limit=15")
    except Exception as e:
        print(f"  [{wallet['name']}] API error: {e}")
        return 0

    new_trades = []
    for t in (trades or []):
        txn_hash = t.get('transactionHash', '')
        if not txn_hash or is_txn_seen(db, txn_hash):
            continue
        trade_ts = int(t.get('timestamp', 0))
        if ms and ms > 0 and trade_ts < ms:
            # Mark as seen (skip historical)
            db.execute("INSERT OR IGNORE INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome) VALUES (?,?,?,?,?,0,'HISTORICAL',?,?)",
                       (wallet_id, txn_hash, t.get('side','?'), float(t.get('size',0)), float(t.get('price',0)), t.get('slug',''), t.get('outcome','?')))
            db.commit()
            continue
        new_trades.append(t)

    if len(new_trades) > MAX_TRADES_PER_SCAN:
        new_trades = new_trades[-MAX_TRADES_PER_SCAN:]

    acct = f"copy-{wallet['name']}"
    processed = 0
    filled_count = 0

    for tr in new_trades:
        side = tr.get('side', 'BUY').upper()
        slug = tr.get('slug', '')
        outcome = tr.get('outcome', 'Yes')
        size = float(tr.get('size', 0))
        whale_price = float(tr.get('price', 0.5))
        txn_hash = tr.get('transactionHash', '')

        whale_notional = size * whale_price
        sim_usd = round(min(max(whale_notional * 0.02, 1.0), INITIAL_CAPITAL * 0.05), 2)

        ts = tr.get('timestamp', '')
        try:
            ts = datetime.utcfromtimestamp(int(ts)).isoformat() if ts else datetime.now().isoformat()
        except Exception:
            ts = datetime.now().isoformat()

        pre_bal = ensure_account(acct)
        trade_side = 'buy' if side == 'BUY' else 'sell'

        # Position dedup: skip BUY if we already hold this market+outcome
        if side == 'BUY' and has_position(acct, slug, outcome):
            log_trade(db, wallet_id,
                      txn_hash=txn_hash, side=side, size=size, whale_price=whale_price,
                      sim_usd=0, fill_price=None, status='SKIPPED',
                      slippage=0, pnl_realized=0,
                      slug=slug, outcome=outcome, timestamp=ts)
            print(f"    {side} SKIP (already holding {outcome} in {slug[:30]})")
            processed += 1
            continue

        # SELL guard: skip if we don't hold this position
        if side == 'SELL' and not has_position(acct, slug, outcome):
            log_trade(db, wallet_id,
                      txn_hash=txn_hash, side=side, size=size, whale_price=whale_price,
                      sim_usd=0, fill_price=None, status='SKIPPED',
                      slippage=0, pnl_realized=0,
                      slug=slug, outcome=outcome, timestamp=ts)
            print(f"    {side} SKIP (no position to sell for {outcome} in {slug[:30]})")
            processed += 1
            continue

        # Expiry check: skip markets expiring within 1 hour
        if _is_market_expiring(slug, 3600):
            log_trade(db, wallet_id,
                      txn_hash=txn_hash, side=side, size=size, whale_price=whale_price,
                      sim_usd=0, fill_price=None, status='SKIPPED',
                      slippage=0, pnl_realized=0,
                      slug=slug, outcome=outcome, timestamp=ts)
            expiry_ts = _extract_expiry(slug)
            print(f"    {side} SKIP (market expires soon, ts={expiry_ts})")
            processed += 1
            continue

        # Skip known closed markets
        if _is_market_closed(db, slug):
            log_trade(db, wallet_id,
                      txn_hash=txn_hash, side=side, size=size, whale_price=whale_price,
                      sim_usd=0, fill_price=None, status='SKIPPED',
                      slippage=0, pnl_realized=0,
                      slug=slug, outcome=outcome, timestamp=ts)
            print(f"    {side} SKIP (market closed: {slug[:30]})")
            processed += 1
            continue

        result = place_market_order(acct, slug, outcome, trade_side, sim_usd)
        post_bal = ensure_account(acct)

        if result and result.get('ok') and result.get('data', {}).get('trade'):
            td = result['data']['trade']
            fill_price = td.get('avg_price', whale_price)
            fill_shares = td.get('shares', 0)

            # Price sanity check: skip if fill deviates >30% from whale (stale/expired market)
            price_gap_pct = abs(fill_price - whale_price) / whale_price * 100 if whale_price > 0 else 0
            if price_gap_pct > 30:
                log_trade(db, wallet_id,
                          txn_hash=txn_hash, side=side, size=size, whale_price=whale_price,
                          sim_usd=0, fill_price=fill_price, status='SKIPPED',
                          slippage=round(price_gap_pct, 2), pnl_realized=0,
                          slug=slug, outcome=outcome, timestamp=ts)
                print(f"    {side} SKIP (price gap {price_gap_pct:.0f}%: whale={whale_price:.4f} fill={fill_price:.4f})")
                processed += 1
                continue

            # Compute slippage: absolute price difference
            fill_slippage = round(abs(fill_price - whale_price), 6)

            pnl_realized = 0.0
            if side == 'SELL':
                cost, _ = get_cost_basis(db, wallet_id, slug)
                pnl_realized = round((fill_price - cost) * fill_shares, 2) if cost > 0 else 0.0

            log_trade(db, wallet_id,
                      txn_hash=txn_hash, side=side, size=size, whale_price=whale_price,
                      sim_usd=sim_usd, fill_price=fill_price, status='FILLED',
                      slippage=fill_slippage, pnl_realized=pnl_realized,
                      slug=slug, outcome=outcome, timestamp=ts)
            print(f"    {side} ${sim_usd:.2f} FILLED @ {fill_price} (whale={whale_price})")
            filled_count += 1
        else:
            err = str(result.get('error', '')) if result else 'no response'
            status = 'SKIPPED' if ('not found' in err.lower() or 'MARKET_NOT_FOUND' in err) else 'FAILED'
            if status == 'SKIPPED':
                _mark_market_closed(db, slug)
            log_trade(db, wallet_id,
                      txn_hash=txn_hash, side=side, size=size, whale_price=whale_price,
                      sim_usd=0, fill_price=None, status=status,
                      slippage=0, pnl_realized=0,
                      slug=slug, outcome=outcome, timestamp=ts)
            print(f"    {side} ${sim_usd:.2f} {status} ({err[:40]})")

        processed += 1

    if filled_count > 0:
        snapshot_pnl(db, wallet_id, acct)

    return processed

def scan_loop():
    """Background thread: continuously scan all active wallets for new trades."""
    db = get_db()
    monitor_start = int(datetime.now().timestamp())

    print(f"Scanner started. Monitor start: {monitor_start}")
    scan_num = 0

    while True:
        scan_num += 1
        scan_start = datetime.now()
        print(f"\n--- Scan #{scan_num} {scan_start.strftime('%H:%M:%S')} ---")

        db.execute("INSERT INTO scan_log (scan_start) VALUES (?)", (scan_start.isoformat(),))
        db.commit()
        scan_log_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        wallets = db.execute("SELECT * FROM wallets WHERE active = 1").fetchall()
        total_new = 0

        for w in wallets:
            wallet_dict = {"address": w['address'], "name": w['name'], "category": w['category']}
            total_new += scan_wallet(db, wallet_dict, monitor_start)

        scan_end = datetime.now()
        elapsed = (scan_end - scan_start).total_seconds()
        db.execute("UPDATE scan_log SET scan_end=?, new_trades_found=?, status=? WHERE id=?",
                   (scan_end.isoformat(), total_new, 'ok', scan_log_id))
        db.commit()

        print(f"  Scan done in {elapsed:.1f}s | New trades: {total_new}")

        # Broadcast P&L update via WebSocket
        if _ws_manager:
            pnl_data = []
            for w_row in wallets:
                pnl_row = db.execute(
                    "SELECT * FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
                    (w_row["id"],)
                ).fetchone()
                if pnl_row:
                    pnl_data.append({"name": w_row["name"], "wallet_id": w_row["id"],
                                     "cash": pnl_row["cash"], "total_value": pnl_row["total_value"],
                                     "pnl": pnl_row["pnl"], "pnl_pct": pnl_row["pnl_pct"]})
            try:
                import asyncio as _asyncio
                _asyncio.run(_ws_manager.broadcast({"type": "pnl_update", "wallets": pnl_data}))
            except Exception:
                pass

        print(f"  Next scan in {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)
