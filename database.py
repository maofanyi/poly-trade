"""SQLite database initialization and connection management."""
import sqlite3
import os
import threading
from config import DB_PATH

_local = threading.local()


def _ensure_data_dir():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

def get_db() -> sqlite3.Connection:
    """Get thread-local database connection."""
    if not hasattr(_local, 'db') or _local.db is None:
        _ensure_data_dir()
        if DB_PATH == ':memory:':
            import urllib.parse
            uri = 'file:memory?cache=shared&mode=memory'
            _local.db = sqlite3.connect(uri, uri=True)
        else:
            _local.db = sqlite3.connect(DB_PATH)
        _local.db.row_factory = sqlite3.Row
        _local.db.execute("PRAGMA journal_mode=WAL")
        _local.db.execute("PRAGMA foreign_keys=ON")
    return _local.db

def init_db():
    """Create all tables if they don't exist.

    Uses individual db.execute() calls instead of executescript() because
    executescript() issues an implicit COMMIT that releases any active
    SAVEPOINT, breaking test-isolation fixtures that wrap tests in savepoints.
    CREATE TABLE IF NOT EXISTS is a DDL statement that only auto-commits
    when it actually creates a table; when the table already exists, no
    implicit commit is issued, and no explicit commit is needed.
    """
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY,
            address TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Unknown',
            active INTEGER DEFAULT 1,
            paused INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY,
            wallet_id INTEGER NOT NULL REFERENCES wallets(id),
            txn_hash TEXT UNIQUE,
            side TEXT NOT NULL,
            size REAL DEFAULT 0,
            whale_price REAL DEFAULT 0,
            sim_usd REAL DEFAULT 0,
            fill_price REAL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            slippage REAL DEFAULT 0,
            pnl_realized REAL DEFAULT 0,
            slug TEXT,
            outcome TEXT,
            timestamp TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS pnl_snapshots (
            id INTEGER PRIMARY KEY,
            wallet_id INTEGER NOT NULL REFERENCES wallets(id),
            cash REAL DEFAULT 0,
            total_value REAL DEFAULT 0,
            pnl REAL DEFAULT 0,
            pnl_pct REAL DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY,
            scan_start TEXT,
            scan_end TEXT,
            new_trades_found INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok'
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS alert_config (
            id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            pnl_threshold_pct REAL DEFAULT -20.0,
            single_loss_usd REAL DEFAULT 10.0,
            webhook_type TEXT,
            webhook_url TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY,
            alert_type TEXT NOT NULL,
            wallet_id INTEGER REFERENCES wallets(id),
            message TEXT,
            sent_via TEXT DEFAULT 'toast',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS wallet_scores (
            wallet_id INTEGER PRIMARY KEY REFERENCES wallets(id),
            trades INTEGER DEFAULT 0,
            volume REAL DEFAULT 0,
            markets INTEGER DEFAULT 0,
            buy_pct REAL DEFAULT 0,
            score REAL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS discovered_wallets (
            address TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            trades INTEGER DEFAULT 0,
            volume REAL DEFAULT 0,
            markets INTEGER DEFAULT 0,
            score REAL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            outcome TEXT NOT NULL,
            price REAL NOT NULL,
            recorded_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS closed_markets (
            slug TEXT PRIMARY KEY,
            detected_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY,
            wallet_id INTEGER REFERENCES wallets(id),
            slug TEXT NOT NULL,
            outcome TEXT NOT NULL,
            whale_shares REAL DEFAULT 0,
            our_shares REAL DEFAULT 0,
            avg_cost REAL DEFAULT 0,
            last_trade_ts TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(wallet_id, slug, outcome)
        )
    """)
    # No explicit commit — CREATE TABLE IF NOT EXISTS is DDL that
    # auto-commits when it actually creates a table.  When tables already
    # exist it is a no-op, so active SAVEPOINTs survive.  An explicit
    # COMMIT would release those savepoints.
    migrate()

def migrate():
    """Add any missing columns (idempotent)."""
    db = get_db()
    cols = [r[1] for r in db.execute("PRAGMA table_info(wallets)").fetchall()]
    if 'paused' not in cols:
        db.execute("ALTER TABLE wallets ADD COLUMN paused INTEGER DEFAULT 0")
        db.commit()
    trade_cols = [r[1] for r in db.execute("PRAGMA table_info(trade_log)").fetchall()]
    if 'skip_reason' not in trade_cols:
        db.execute("ALTER TABLE trade_log ADD COLUMN skip_reason TEXT")
        db.commit()
    alert_cols = [r[1] for r in db.execute("PRAGMA table_info(alert_config)").fetchall()]
    if 'monitor_start' not in alert_cols:
        db.execute("ALTER TABLE alert_config ADD COLUMN monitor_start INTEGER")
        db.commit()
    wallet_cols = [r[1] for r in db.execute("PRAGMA table_info(wallets)").fetchall()]
    if 'started_at' not in wallet_cols:
        db.execute("ALTER TABLE wallets ADD COLUMN started_at TEXT")
        db.commit()


def backfill_positions():
    """One-time backfill of positions table from existing trade_log (last 7 days only)."""
    db = get_db()
    wallets = db.execute("SELECT id FROM wallets WHERE active = 1").fetchall()
    for w in wallets:
        trades = db.execute("""
            SELECT slug, outcome, side, fill_price, size, sim_usd, timestamp
            FROM trade_log
            WHERE wallet_id = ? AND status = 'FILLED'
              AND timestamp >= datetime('now', '-7 days', 'localtime')
              AND slug NOT IN (SELECT slug FROM closed_markets)
            ORDER BY id ASC
        """, (w['id'],)).fetchall()
        for t in trades:
            slug = t['slug'] or ''
            outcome = t['outcome'] or ''
            if not slug or not outcome:
                continue
            side = (t['side'] or 'BUY').upper()
            size = float(t['size'] or 0)
            price = float(t['fill_price'] or 0)
            ts = t['timestamp'] or ''
            if side == 'BUY':
                delta = size
            else:
                delta = -size
            # whale_shares tracks the whale's net position from trade_log.
            # our_shares stays 0 — our actual holdings come from pm-trader (get_portfolio).
            db.execute("""
                INSERT INTO positions (wallet_id, slug, outcome, whale_shares, our_shares, avg_cost, last_trade_ts)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(wallet_id, slug, outcome) DO UPDATE SET
                    whale_shares = whale_shares + ?,
                    avg_cost = CASE WHEN whale_shares + ? > 0
                        THEN (avg_cost * whale_shares + ? * ?) / (whale_shares + ?)
                        ELSE ? END,
                    last_trade_ts = MAX(last_trade_ts, ?),
                    updated_at = datetime('now','localtime')
            """, (w['id'], slug, outcome, max(delta, 0), price, ts,
                  max(delta, 0),
                  max(delta, 0), price, size, max(delta, 0), price,
                  ts))
    db.execute("""
        UPDATE wallets SET started_at = (
            SELECT MIN(timestamp) FROM trade_log
            WHERE trade_log.wallet_id = wallets.id AND status = 'FILLED'
        ) WHERE started_at IS NULL
          AND id IN (SELECT DISTINCT wallet_id FROM trade_log WHERE status = 'FILLED')
    """)
    db.execute("UPDATE wallets SET started_at = created_at WHERE started_at IS NULL")
    db.commit()
