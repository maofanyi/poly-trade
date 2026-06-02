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
    """Create all tables if they don't exist."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY,
            address TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Unknown',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

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
        );

        CREATE TABLE IF NOT EXISTS pnl_snapshots (
            id INTEGER PRIMARY KEY,
            wallet_id INTEGER NOT NULL REFERENCES wallets(id),
            cash REAL DEFAULT 0,
            total_value REAL DEFAULT 0,
            pnl REAL DEFAULT 0,
            pnl_pct REAL DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY,
            scan_start TEXT,
            scan_end TEXT,
            new_trades_found INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok'
        );

        CREATE TABLE IF NOT EXISTS alert_config (
            id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            pnl_threshold_pct REAL DEFAULT -20.0,
            single_loss_usd REAL DEFAULT 10.0,
            webhook_type TEXT,
            webhook_url TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY,
            alert_type TEXT NOT NULL,
            wallet_id INTEGER REFERENCES wallets(id),
            message TEXT,
            sent_via TEXT DEFAULT 'toast',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS wallet_scores (
            wallet_id INTEGER PRIMARY KEY REFERENCES wallets(id),
            trades INTEGER DEFAULT 0,
            volume REAL DEFAULT 0,
            markets INTEGER DEFAULT 0,
            buy_pct REAL DEFAULT 0,
            score REAL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    db.commit()
