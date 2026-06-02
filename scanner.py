"""Trade scanning loop — fetches trades, executes via pm-trader, persists to DB."""
import json
import time
import urllib.request
from datetime import datetime
from config import DATA_API, INITIAL_CAPITAL, MAX_TRADES_PER_SCAN, SCAN_INTERVAL
from database import get_db
import re
from trader import ensure_account, place_market_order, has_position

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

def snapshot_pnl(db, wallet_id: int, acct_name: str):
    """Take a P&L snapshot for one wallet."""
    bal = ensure_account(acct_name)
    total_val = round(bal['total_value'], 2)
    cash_val = round(bal['cash'], 2)
    pnl_val = round(total_val - INITIAL_CAPITAL, 2)
    pnl_pct = round(pnl_val / INITIAL_CAPITAL * 100, 2)
    db.execute("""
        INSERT INTO pnl_snapshots (wallet_id, cash, total_value, pnl, pnl_pct)
        VALUES (?, ?, ?, ?, ?)
    """, (wallet_id, cash_val, total_val, pnl_val, pnl_pct))
    db.commit()

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


def scan_wallet(db, wallet: dict, ms: int) -> int:
    """Scan one wallet for new trades. Returns count of new trades processed."""
    wallet_id = get_wallet_id(db, wallet['name'])
    if not wallet_id:
        return 0

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
