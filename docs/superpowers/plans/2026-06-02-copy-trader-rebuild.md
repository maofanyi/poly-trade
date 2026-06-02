# Polymarket Copy-Trading Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full rebuild of Polymarket copy-trading bot with FastAPI backend, Vue 3 dashboard, SQLite storage, WebSocket real-time updates, and Docker deployment.

**Architecture:** Single FastAPI process with background scanner thread, SQLite for persistence, WebSocket for real-time push, Vue 3 CDN SPA served as static files. Backend modules cleanly separated by responsibility.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, SQLite (stdlib), Vue 3 (CDN import-map), ECharts (CDN), pm-trader CLI, Docker.

---

## Phase 1: Foundations

### Task 1: Config module (`config.py`)

**Files:**
- Create: `G:\trade\config.py`

- [ ] **Step 1: Write `config.py`**

```python
"""Application constants."""
import os

# Polymarket Data API
DATA_API = "https://data-api.polymarket.com"

# pm-trader CLI
PM_TRADER = "pm-trader"

# Trading parameters
INITIAL_CAPITAL = 500.0
MAX_TRADES_PER_SCAN = 2
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", "120"))

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "trade.db"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Monitor start — set at boot, skip trades before this
MONITOR_START = None

# Default 26 candidate wallets (for seed)
DEFAULT_WALLETS = [
    {"address": "0x15ceffed7bf820cd2d90f90ea24ae9909f5cd5fa", "name": "HondaCivic", "category": "Weather"},
    {"address": "0x57ee70867b4e387de9de34fd62bc685aa02a8112", "name": "ikik111", "category": "Weather"},
    {"address": "0x1f66796b45581868376365aef54b51eb84184c8d", "name": "Maskache2", "category": "Weather"},
    {"address": "0x1838cca016850ac7185a9b149fe7d0bd2d6629b4", "name": "JoeTheMeteorologist", "category": "Weather"},
    {"address": "0x331bf91c132af9d921e1908ca0979363fc47193f", "name": "BeefSlayer", "category": "Weather"},
    {"address": "0xd75d96a23515172778d3281f53c9180b985100c8", "name": "Varyage", "category": "Weather"},
    {"address": "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f", "name": "wokerjoesleeper", "category": "Politics"},
    {"address": "0x38e59b36aae31b164200d0cad7c3fe5e0ee795e7", "name": "cowcat", "category": "Politics"},
    {"address": "0x07921379f7b31ef93da634b688b2fe36897db778", "name": "ewelmealt", "category": "Sports"},
    {"address": "0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5", "name": "EFFICIENCYEXPERT", "category": "Sports"},
]
```

- [ ] **Step 2: Verify import**

```bash
python -c "from config import DATA_API, INITIAL_CAPITAL; print(DATA_API, INITIAL_CAPITAL)"
```
Expected: prints URL and 500.0

- [ ] **Step 3: Commit**

```bash
git add config.py && git commit -m "feat: add config module with constants and default wallets"
```

---

### Task 2: Database module (`database.py`)

**Files:**
- Create: `G:\trade\database.py`

- [ ] **Step 1: Write `database.py`**

```python
"""SQLite database initialization and connection management."""
import sqlite3
import os
import threading
from config import DB_PATH, BASE_DIR

_local = threading.local()

def _ensure_data_dir():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

def get_db() -> sqlite3.Connection:
    """Get thread-local database connection."""
    if not hasattr(_local, 'db') or _local.db is None:
        _ensure_data_dir()
        _local.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.db.row_factory = sqlite3.Row
        _local.db.execute("PRAGMA journal_mode=WAL")
        _local.db.execute("PRAGMA foreign_keys=ON")
    return _local.db

def init_db():
    """Create all tables if they don't exist."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Unknown',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id INTEGER NOT NULL REFERENCES wallets(id),
            cash REAL DEFAULT 0,
            total_value REAL DEFAULT 0,
            pnl REAL DEFAULT 0,
            pnl_pct REAL DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_start TEXT,
            scan_end TEXT,
            new_trades_found INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok'
        );

        CREATE TABLE IF NOT EXISTS alert_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enabled INTEGER DEFAULT 1,
            pnl_threshold_pct REAL DEFAULT -20.0,
            single_loss_usd REAL DEFAULT 10.0,
            webhook_type TEXT,
            webhook_url TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            wallet_id INTEGER REFERENCES wallets(id),
            message TEXT,
            sent_via TEXT DEFAULT 'toast',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    db.commit()
```

- [ ] **Step 2: Verify database creation**

```bash
python -c "from database import init_db, get_db; init_db(); db=get_db(); tables=db.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall(); print([t[0] for t in tables])"
```
Expected: `['wallets', 'trade_log', 'pnl_snapshots', 'scan_log', 'alert_config', 'alert_log']`

- [ ] **Step 3: Commit**

```bash
git add database.py && git commit -m "feat: add database module with SQLite schema"
```

---

### Task 3: Pydantic models (`models.py`)

**Files:**
- Create: `G:\trade\models.py`

- [ ] **Step 1: Install FastAPI**

```bash
pip install fastapi uvicorn
```

- [ ] **Step 2: Write `models.py`**

```python
"""Pydantic models for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional

class WalletCreate(BaseModel):
    address: str = Field(..., min_length=10, max_length=42)
    name: str = Field(..., min_length=1, max_length=50)
    category: str = Field(default="Unknown", max_length=20)

class WalletOut(BaseModel):
    id: int
    address: str
    name: str
    category: str
    active: bool
    created_at: str
    # Current P&L (joined from latest snapshot)
    cash: Optional[float] = None
    total_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None

class TradeOut(BaseModel):
    id: int
    wallet_id: int
    wallet_name: Optional[str] = None
    txn_hash: Optional[str] = None
    side: str
    size: float
    whale_price: float
    sim_usd: float
    fill_price: Optional[float] = None
    status: str
    slippage: float
    pnl_realized: float
    slug: Optional[str] = None
    outcome: Optional[str] = None
    timestamp: str

class PnlSnapshotOut(BaseModel):
    id: int
    wallet_id: int
    cash: float
    total_value: float
    pnl: float
    pnl_pct: float
    timestamp: str

class AlertConfigUpdate(BaseModel):
    enabled: Optional[int] = None
    pnl_threshold_pct: Optional[float] = None
    single_loss_usd: Optional[float] = None
    webhook_type: Optional[str] = None
    webhook_url: Optional[str] = None

class SummaryOut(BaseModel):
    total_capital: float
    total_cash: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    wallet_count: int
    active_wallet_count: int
    last_scan: Optional[str] = None
    total_trades: int
    win_rate: Optional[float] = None

class StateOut(BaseModel):
    wallets: list[WalletOut]
    trades: list[TradeOut]
    summary: SummaryOut
    last_scan: Optional[str] = None
```

- [ ] **Step 3: Verify import**

```bash
python -c "from models import WalletCreate, TradeOut; print('OK')"
```
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add models.py && git commit -m "feat: add Pydantic models for API validation"
```

---

## Phase 2: Core Logic

### Task 4: Trader wrapper (`trader.py`)

**Files:**
- Create: `G:\trade\trader.py`
- Modify: (none — reuses logic from existing `copy_trader.py`)

- [ ] **Step 1: Write `trader.py`**

```python
"""pm-trader CLI wrapper for paper trading operations."""
import subprocess
import json
import time
from config import PM_TRADER, INITIAL_CAPITAL

def pm(cmd: str) -> dict | None:
    """Execute a pm-trader command, return parsed JSON or None."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout.strip())
    except Exception:
        return None

def ensure_account(acct: str) -> dict:
    """Ensure account exists with INITIAL_CAPITAL, return balance dict."""
    bal = pm(f"{PM_TRADER} --account {acct} balance")
    if not bal or not bal.get('ok'):
        pm(f"{PM_TRADER} --account {acct} init --balance {INITIAL_CAPITAL}")
        return {"cash": INITIAL_CAPITAL, "total_value": INITIAL_CAPITAL, "pnl": 0}
    data = bal.get('data', {})
    return {
        "cash": data.get('cash', 0),
        "total_value": data.get('total_value', 0),
        "pnl": data.get('pnl', 0)
    }

def get_midpoint(slug: str) -> dict | None:
    """Get YES/NO prices for a market slug."""
    r = pm(f'{PM_TRADER} price "{slug}"')
    if r and r.get('ok') and r.get('data'):
        prices = r['data']
        return {
            'YES': prices.get('YES', prices.get('yes')),
            'NO': prices.get('NO', prices.get('no'))
        }
    return None

def place_market_order(acct: str, slug: str, outcome: str, side: str, amount_usd: float) -> dict | None:
    """Place a market order (buy or sell). Returns result or None."""
    if side.upper() == 'BUY':
        cmd = f'{PM_TRADER} --account {acct} buy "{slug}" "{outcome}" {amount_usd}'
    else:
        cmd = f'{PM_TRADER} --account {acct} sell "{slug}" "{outcome}" {amount_usd}'
    return pm(cmd)

def close_position(acct: str, slug: str, outcome: str, shares: float) -> dict | None:
    """Close a position by selling all shares."""
    cmd = f'{PM_TRADER} --account {acct} sell "{slug}" "{outcome}" {shares}'
    return pm(cmd)
```

- [ ] **Step 2: Verify pm-trader is available**

```bash
python -c "from trader import pm; r = pm('pm-trader --help'); print('OK' if r else 'FAIL')"
```
Expected: OK (pm-trader must be installed)

- [ ] **Step 3: Commit**

```bash
git add trader.py && git commit -m "feat: add pm-trader CLI wrapper module"
```

---

### Task 5: Scanner module (`scanner.py`)

**Files:**
- Create: `G:\trade\scanner.py`

- [ ] **Step 1: Write `scanner.py`**

```python
"""Trade scanning loop — fetches trades, executes via pm-trader, persists to DB."""
import json
import time
import urllib.request
from datetime import datetime
from config import DATA_API, INITIAL_CAPITAL, MAX_TRADES_PER_SCAN, SCAN_INTERVAL, MONITOR_START
from database import get_db
from trader import ensure_account, place_market_order

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

        result = place_market_order(acct, slug, outcome, trade_side, sim_usd)
        post_bal = ensure_account(acct)

        if result and result.get('ok') and result.get('data', {}).get('trade'):
            td = result['data']['trade']
            fill_price = td.get('avg_price', whale_price)
            fill_shares = td.get('shares', 0)
            fill_slippage = td.get('slippage', 0)

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

    if new_trades:
        snapshot_pnl(db, wallet_id, acct)

    return processed

def scan_loop():
    """Background thread: continuously scan all active wallets for new trades."""
    from datetime import datetime as dt
    db = get_db()
    monitor_start = int(dt.now().timestamp())

    print(f"Scanner started. Monitor start: {monitor_start}")
    scan_num = 0

    while True:
        scan_num += 1
        scan_start = dt.now()
        print(f"\n--- Scan #{scan_num} {scan_start.strftime('%H:%M:%S')} ---")

        db.execute("INSERT INTO scan_log (scan_start) VALUES (?)", (scan_start.isoformat(),))
        db.commit()
        scan_log_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        wallets = db.execute("SELECT * FROM wallets WHERE active = 1").fetchall()
        total_new = 0

        for w in wallets:
            wallet_dict = {"address": w['address'], "name": w['name'], "category": w['category']}
            total_new += scan_wallet(db, wallet_dict, monitor_start)

        scan_end = dt.now()
        elapsed = (scan_end - scan_start).total_seconds()
        db.execute("UPDATE scan_log SET scan_end=?, new_trades_found=?, status=? WHERE id=?",
                   (scan_end.isoformat(), total_new, 'ok', scan_log_id))
        db.commit()

        print(f"  Scan done in {elapsed:.1f}s | New trades: {total_new}")
        print(f"  Next scan in {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)
```

- [ ] **Step 2: Verify import (no run)**

```bash
python -c "from scanner import scan_wallet, scan_loop; print('OK')"
```
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add scanner.py && git commit -m "feat: add scanner module with trade detection and execution"
```

---

## Phase 3: API Layer

### Task 6: API router init (`api/__init__.py`)

**Files:**
- Create: `G:\trade\api\__init__.py`
- Create: `G:\trade\api\state.py` (placeholder)
- Create: `G:\trade\api\wallets.py` (placeholder)
- Create: `G:\trade\api\trades.py` (placeholder)
- Create: `G:\trade\api\summary.py` (placeholder)

- [ ] **Step 1: Create directory and init**

```bash
New-Item -ItemType Directory -Force -Path G:\trade\api
```

```python
# api/__init__.py
"""API route modules."""
```

- [ ] **Step 2: Commit**

```bash
git add api/__init__.py && git commit -m "feat: add api package init"
```

---

### Task 7: Wallet API (`api/wallets.py`)

**Files:**
- Create: `G:\trade\api\wallets.py`

- [ ] **Step 1: Write `api/wallets.py`**

```python
"""Wallet CRUD API."""
from fastapi import APIRouter, HTTPException
from database import get_db
from models import WalletCreate, WalletOut
from trader import ensure_account

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

def _row_to_out(row, pnl_row=None) -> dict:
    return {
        "id": row["id"], "address": row["address"], "name": row["name"],
        "category": row["category"], "active": bool(row["active"]),
        "created_at": row["created_at"],
        "cash": pnl_row["cash"] if pnl_row else None,
        "total_value": pnl_row["total_value"] if pnl_row else None,
        "pnl": pnl_row["pnl"] if pnl_row else None,
        "pnl_pct": pnl_row["pnl_pct"] if pnl_row else None,
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
```

- [ ] **Step 2: Write test `tests/test_api.py`** (wallet tests)

```python
"""API endpoint tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from main import app
from database import init_db, get_db

client = TestClient(app)
init_db()

def test_list_wallets_empty():
    resp = client.get("/api/wallets")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_add_wallet():
    resp = client.post("/api/wallets", json={
        "address": "0xtest12345678901234567890123456789012345678",
        "name": "TestWallet",
        "category": "Weather"
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

def test_remove_wallet():
    # Add then remove
    client.post("/api/wallets", json={
        "address": "0xremove123456789012345678901234567890123456",
        "name": "RemoveMe",
        "category": "Sports"
    })
    resp = client.delete("/api/wallets/1")  # assumes id 1 exists
    assert resp.status_code in (200, 404)

def test_duplicate_wallet_reactivates():
    addr = "0xdup0123456789012345678901234567890123456789"
    r1 = client.post("/api/wallets", json={"address": addr, "name": "Dup1", "category": "Tech"})
    client.delete(f"/api/wallets/{r1.json()['id']}")
    r2 = client.post("/api/wallets", json={"address": addr, "name": "Dup1", "category": "Tech"})
    assert r2.json().get("reactivated") is True
```

- [ ] **Step 3: Run wallet tests**

```bash
python -m pytest tests/test_api.py::test_list_wallets_empty tests/test_api.py::test_add_wallet -v
```

- [ ] **Step 4: Commit**

```bash
git add api/wallets.py tests/test_api.py && git commit -m "feat: add wallet CRUD API with tests"
```

---

### Task 8: Trades API (`api/trades.py`)

**Files:**
- Create: `G:\trade\api\trades.py`

- [ ] **Step 1: Write `api/trades.py`**

```python
"""Trades listing API."""
from fastapi import APIRouter, Query
from database import get_db
from models import TradeOut

router = APIRouter(prefix="/api/trades", tags=["trades"])

@router.get("")
def list_trades(
    wallet_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    db = get_db()
    conditions = []
    params = {}

    if wallet_id is not None:
        conditions.append("t.wallet_id = :wallet_id")
        params["wallet_id"] = wallet_id
    if status is not None:
        conditions.append("t.status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params["limit"] = limit
    params["offset"] = offset

    rows = db.execute(f"""
        SELECT t.*, w.name as wallet_name
        FROM trade_log t JOIN wallets w ON t.wallet_id = w.id
        {where}
        ORDER BY t.id DESC
        LIMIT :limit OFFSET :offset
    """, params).fetchall()

    total = db.execute(f"""
        SELECT COUNT(*) FROM trade_log t
        {where.replace('t.wallet_id', 't.wallet_id').replace('t.status', 't.status')}
    """, params).fetchone()[0]

    return {
        "trades": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset
    }
```

- [ ] **Step 2: Add tests to `tests/test_api.py`**

```python
def test_list_trades():
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data
    assert "total" in data

def test_trades_filter_by_status():
    resp = client.get("/api/trades?status=FILLED")
    assert resp.status_code == 200

def test_trades_pagination():
    resp = client.get("/api/trades?limit=5&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()["trades"]) <= 5
```

- [ ] **Step 3: Run trades tests**

```bash
python -m pytest tests/test_api.py::test_list_trades -v
```

- [ ] **Step 4: Commit**

```bash
git add api/trades.py && git commit -m "feat: add trades listing API with pagination"
```

---

### Task 9: Summary API (`api/summary.py`)

**Files:**
- Create: `G:\trade\api\summary.py`

- [ ] **Step 1: Write `api/summary.py`**

```python
"""Summary / aggregate API."""
from fastapi import APIRouter
from database import get_db
from config import INITIAL_CAPITAL

router = APIRouter(prefix="/api", tags=["summary"])

@router.get("/summary")
def get_summary():
    db = get_db()
    wallets = db.execute("SELECT id FROM wallets WHERE active = 1").fetchall()

    wallet_count = len(wallets)
    total_capital = INITIAL_CAPITAL * wallet_count

    total_cash = 0.0
    total_value = 0.0

    for w in wallets:
        pnl = db.execute(
            "SELECT cash, total_value FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
            (w["id"],)
        ).fetchone()
        if pnl:
            total_cash += pnl["cash"] or 0
            total_value += pnl["total_value"] or 0

    total_pnl = round(total_value - total_capital, 2)
    total_pnl_pct = round(total_pnl / total_capital * 100, 2) if total_capital > 0 else 0.0

    total_trades = db.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    filled = db.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'FILLED'").fetchone()[0]
    wins = db.execute("SELECT COUNT(*) FROM trade_log WHERE status = 'FILLED' AND pnl_realized > 0").fetchone()[0]
    win_rate = round(wins / filled * 100, 2) if filled > 0 else None

    last_scan = db.execute("SELECT scan_end FROM scan_log ORDER BY id DESC LIMIT 1").fetchone()

    return {
        "total_capital": total_capital,
        "total_cash": round(total_cash, 2),
        "total_value": round(total_value, 2),
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "wallet_count": wallet_count,
        "active_wallet_count": wallet_count,
        "last_scan": last_scan["scan_end"] if last_scan else None,
        "total_trades": total_trades,
        "win_rate": win_rate
    }
```

- [ ] **Step 2: Add test**

```python
def test_get_summary():
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_capital" in data
    assert "total_pnl" in data
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/test_api.py::test_get_summary -v
```

- [ ] **Step 4: Commit**

```bash
git add api/summary.py && git commit -m "feat: add summary API with aggregate stats"
```

---

### Task 10: State API (`api/state.py`)

**Files:**
- Create: `G:\trade\api\state.py`

- [ ] **Step 1: Write `api/state.py`**

```python
"""Full state snapshot API."""
from fastapi import APIRouter
from database import get_db
from config import INITIAL_CAPITAL

router = APIRouter(prefix="/api", tags=["state"])

@router.get("/state")
def get_state():
    db = get_db()

    wallets = db.execute("SELECT * FROM wallets WHERE active = 1 ORDER BY name").fetchall()
    wallet_list = []
    total_cash = 0.0
    total_value = 0.0

    for w in wallets:
        pnl = db.execute(
            "SELECT * FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
            (w["id"],)
        ).fetchone()
        wallet_list.append({
            "id": w["id"], "address": w["address"], "name": w["name"],
            "category": w["category"], "active": bool(w["active"]),
            "created_at": w["created_at"],
            "cash": pnl["cash"] if pnl else None,
            "total_value": pnl["total_value"] if pnl else None,
            "pnl": pnl["pnl"] if pnl else None,
            "pnl_pct": pnl["pnl_pct"] if pnl else None,
        })
        if pnl:
            total_cash += pnl["cash"] or 0
            total_value += pnl["total_value"] or 0

    wallet_count = len(wallet_list)
    total_capital = INITIAL_CAPITAL * wallet_count
    total_pnl = round(total_value - total_capital, 2)
    total_pnl_pct = round(total_pnl / total_capital * 100, 2) if total_capital > 0 else 0.0

    trades = db.execute("""
        SELECT t.*, w.name as wallet_name
        FROM trade_log t JOIN wallets w ON t.wallet_id = w.id
        ORDER BY t.id DESC LIMIT 100
    """).fetchall()

    last_scan = db.execute("SELECT scan_end FROM scan_log ORDER BY id DESC LIMIT 1").fetchone()
    total_trades = db.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]

    return {
        "wallets": wallet_list,
        "trades": [dict(t) for t in trades],
        "summary": {
            "total_capital": total_capital,
            "total_cash": round(total_cash, 2),
            "total_value": round(total_value, 2),
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "wallet_count": wallet_count,
            "active_wallet_count": wallet_count,
            "last_scan": last_scan["scan_end"] if last_scan else None,
            "total_trades": total_trades,
            "win_rate": None
        },
        "last_scan": last_scan["scan_end"] if last_scan else None
    }
```

- [ ] **Step 2: Add test**

```python
def test_get_state():
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "wallets" in data
    assert "trades" in data
    assert "summary" in data
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/test_api.py::test_get_state -v
```

- [ ] **Step 4: Commit**

```bash
git add api/state.py && git commit -m "feat: add state snapshot API"
```

---

### Task 11: Health API (add to `api/state.py`)

**Files:**
- Modify: `G:\trade\api\state.py`

- [ ] **Step 1: Add health endpoint**

Add to `api/state.py`:

```python
@router.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Commit**

```bash
git add api/state.py && git commit -m "feat: add health check endpoint"
```

---

### Task 12: WebSocket module (`websocket.py`)

**Files:**
- Create: `G:\trade\websocket.py`

- [ ] **Step 1: Write `websocket.py`**

```python
"""WebSocket manager for real-time dashboard updates."""
import asyncio
import json
from fastapi import WebSocket

class WSManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, msg: dict):
        payload = json.dumps(msg, ensure_ascii=False, default=str)
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def heartbeat(self):
        """Send ping every 30s."""
        while True:
            await asyncio.sleep(30)
            await self.broadcast({"type": "ping"})

ws_manager = WSManager()
```

- [ ] **Step 2: Commit**

```bash
git add websocket.py && git commit -m "feat: add WebSocket manager"
```

---

### Task 13: Alerts module (`alerts.py`)

**Files:**
- Create: `G:\trade\alerts.py`

- [ ] **Step 1: Write `alerts.py`**

```python
"""Alert engine: threshold checks and webhook delivery."""
import json
import urllib.request
from datetime import datetime, timedelta
from database import get_db

def get_config(db) -> dict:
    row = db.execute("SELECT * FROM alert_config WHERE id = 1").fetchone()
    if not row:
        db.execute("INSERT INTO alert_config (id) VALUES (1)")
        db.commit()
        return {"enabled": 1, "pnl_threshold_pct": -20.0, "single_loss_usd": 10.0, "webhook_type": None, "webhook_url": None}
    return dict(row)

def update_config(db, **kwargs):
    sets = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [1]
    db.execute(f"UPDATE alert_config SET {sets}, updated_at=datetime('now','localtime') WHERE id=?", values)
    db.commit()

def was_alerted_recently(db, alert_type: str, wallet_id: int, hours: int = 1) -> bool:
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    row = db.execute(
        "SELECT id FROM alert_log WHERE alert_type=? AND wallet_id=? AND created_at > ? LIMIT 1",
        (alert_type, wallet_id, since)
    ).fetchone()
    return row is not None

def log_alert(db, alert_type: str, wallet_id: int | None, message: str, sent_via: str = "toast"):
    db.execute(
        "INSERT INTO alert_log (alert_type, wallet_id, message, sent_via) VALUES (?,?,?,?)",
        (alert_type, wallet_id, message, sent_via)
    )
    db.commit()

def send_webhook(webhook_type: str, webhook_url: str, message: str):
    """Send alert via webhook (Bark/Telegram/WeCom)."""
    try:
        if webhook_type == 'bark':
            import urllib.parse
            url = f"{webhook_url}/{urllib.parse.quote(message)}"
            urllib.request.urlopen(url, timeout=5)
        elif webhook_type == 'telegram':
            # Telegram Bot API: POST to webhook_url with chat_id + text
            data = json.dumps({"text": message, "parse_mode": "HTML"}).encode()
            req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
        elif webhook_type == 'wecom':
            # WeCom bot: POST markdown message
            data = json.dumps({"msgtype": "markdown", "markdown": {"content": message}}).encode()
            req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Webhook error ({webhook_type}): {e}")

async def check_alerts(ws_manager, wallet_name: str, wallet_id: int):
    """Check alert thresholds after a trade. Call after each trade."""
    db = get_db()
    cfg = get_config(db)
    if not cfg['enabled']:
        return

    # Check single trade loss
    last_trade = db.execute(
        "SELECT pnl_realized, sim_usd FROM trade_log WHERE wallet_id=? AND status='FILLED' ORDER BY id DESC LIMIT 1",
        (wallet_id,)
    ).fetchone()
    if last_trade and last_trade['pnl_realized'] and abs(last_trade['pnl_realized']) > cfg['single_loss_usd']:
        msg = f"⚠️ {wallet_name} 单笔亏损 ${last_trade['pnl_realized']:.2f}"
        if not was_alerted_recently(db, 'single_trade_loss', wallet_id):
            log_alert(db, 'single_trade_loss', wallet_id, msg, 'toast')
            await ws_manager.broadcast({"type": "alert", "alert_type": "single_trade_loss", "wallet_name": wallet_name, "message": msg})
            if cfg.get('webhook_url'):
                send_webhook(cfg['webhook_type'], cfg['webhook_url'], msg)
                log_alert(db, 'single_trade_loss', wallet_id, msg, 'webhook')

    # Check wallet P&L threshold
    pnl = db.execute(
        "SELECT pnl_pct FROM pnl_snapshots WHERE wallet_id=? ORDER BY id DESC LIMIT 1",
        (wallet_id,)
    ).fetchone()
    if pnl and pnl['pnl_pct'] is not None and pnl['pnl_pct'] <= cfg['pnl_threshold_pct']:
        msg = f"🔴 {wallet_name} 亏损超过阈值: {pnl['pnl_pct']:.1f}%"
        if not was_alerted_recently(db, 'wallet_loss', wallet_id):
            log_alert(db, 'wallet_loss', wallet_id, msg, 'toast')
            await ws_manager.broadcast({"type": "alert", "alert_type": "wallet_loss", "wallet_name": wallet_name, "message": msg})
            if cfg.get('webhook_url'):
                send_webhook(cfg['webhook_type'], cfg['webhook_url'], msg)
                log_alert(db, 'wallet_loss', wallet_id, msg, 'webhook')
```

- [ ] **Step 2: Commit**

```bash
git add alerts.py && git commit -m "feat: add alert engine with webhook support"
```

---

## Phase 4: Main App

### Task 14: FastAPI main entry (`main.py`)

**Files:**
- Create: `G:\trade\main.py`

- [ ] **Step 1: Write `main.py`**

```python
"""FastAPI application entry point."""
import asyncio
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from database import init_db, get_db
from websocket import ws_manager
from scanner import scan_loop
from api.wallets import router as wallets_router
from api.trades import router as trades_router
from api.state import router as state_router
from api.summary import router as summary_router
from config import STATIC_DIR
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_db()
    # Seed defaults
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] == 0:
        from config import DEFAULT_WALLETS
        for w in DEFAULT_WALLETS:
            db.execute(
                "INSERT OR IGNORE INTO wallets (address, name, category) VALUES (?, ?, ?)",
                (w["address"], w["name"], w["category"])
            )
        db.commit()
        print(f"Seeded {len(DEFAULT_WALLETS)} default wallets")
    # Ensure alert_config row exists
    db.execute("INSERT OR IGNORE INTO alert_config (id) VALUES (1)")
    db.commit()

    # Start scanner (skip in test mode)
    if os.environ.get("SCAN_ENABLED", "1") != "0":
        scanner_thread = threading.Thread(target=scan_loop, daemon=True)
        scanner_thread.start()

    # Start heartbeat
    asyncio.create_task(ws_manager.heartbeat())

    yield
    print("Shutting down...")

app = FastAPI(title="Polymarket Copy Trader", lifespan=lifespan)

# Mount API routers
app.include_router(wallets_router)
app.include_router(trades_router)
app.include_router(state_router)
app.include_router(summary_router)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            # Client sends pong in response to ping
            if data == 'pong':
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

# Serve static files
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8766, reload=True)
```

- [ ] **Step 2: Start server to verify**

```bash
python main.py
```
Expected: Server starts on :8766. Visit http://localhost:8766/api/health → `{"status":"ok"}`. Then Ctrl+C to stop.

- [ ] **Step 3: Commit**

```bash
git add main.py && git commit -m "feat: add FastAPI main entry with router mounting and lifespan"
```

---

### Task 15: Wire scanner to WebSocket

**Files:**
- Modify: `G:\trade\scanner.py`
- Modify: `G:\trade\main.py`

- [ ] **Step 1: Add WebSocket broadcast to scanner**

In `scanner.py`, add at the top:

```python
# Deferred import to avoid circular dependency
_ws_manager = None

def set_ws_manager(mgr):
    global _ws_manager
    _ws_manager = mgr
```

After each scan cycle in `scan_loop()`, after the P&L snapshot, add:

```python
        if _ws_manager:
            import asyncio
            # Send P&L update via WebSocket
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
            asyncio.run(_ws_manager.broadcast({"type": "pnl_update", "wallets": pnl_data}))
```

In `main.py`, after scanner_thread start:

```python
    from scanner import set_ws_manager
    set_ws_manager(ws_manager)
```

- [ ] **Step 2: Commit**

```bash
git add scanner.py main.py && git commit -m "feat: wire scanner to WebSocket for real-time P&L updates"
```

---

## Phase 5: Frontend Shell

### Task 16: HTML shell (`static/index.html`)

**Files:**
- Create: `G:\trade\static\index.html`

- [ ] **Step 1: Write `index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Polymarket 跟单监控面板</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>">
<script type="importmap">
{
  "imports": {
    "vue": "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js",
    "echarts": "https://unpkg.com/echarts@5/dist/echarts.esm.min.js"
  }
}
</script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0a0e14; --card: #111821; --border: #1c2838; --border-light: #263246;
  --green: #00e676; --red: #ff3d4f; --amber: #ffab00; --blue: #448aff;
  --text: #e4ecf5; --muted: #5a6b7d;
  --radius: 8px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d131c; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #1c2838; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a3f58; }

body {
  background: var(--bg); color: var(--text);
  font-family: 'Noto Sans SC', 'JetBrains Mono', sans-serif;
  padding: 16px 20px; min-height: 100vh;
}

/* Utility classes */
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); }
.green { color: var(--green); } .red { color: var(--red); } .amber { color: var(--amber); } .blue { color: var(--blue); }
.mono { font-family: 'JetBrains Mono', monospace; }
.muted { color: var(--muted); }

h1 { font-size: 18px; margin-bottom: 2px; color: var(--green); font-family: 'JetBrains Mono', monospace; letter-spacing: 1px; }
.sub { font-size: 12px; color: var(--muted); margin-bottom: 14px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }

.pulse { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--green); animation: pulse 1.5s ease infinite; margin-right: 4px; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Tabs */
.tabs { display: flex; gap: 4px; margin-bottom: 14px; }
.tab { padding: 7px 18px; border: 1px solid var(--border); border-radius: 6px; background: var(--card); color: var(--muted); cursor: pointer; font-family: inherit; font-size: 13px; transition: all 0.2s; }
.tab:hover { border-color: var(--border-light); color: var(--text); }
.tab.active { border-color: var(--green); color: var(--green); background: rgba(0,230,118,0.06); }

.tab-content { display: none; }
.tab-content.active { display: block; }

/* Summary */
.summary-bar { display: flex; gap: 24px; padding: 12px 18px; margin-bottom: 12px; background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); flex-wrap: wrap; }
.summary-item { display: flex; flex-direction: column; gap: 2px; }
.summary-label { font-size: 11px; color: var(--muted); }
.summary-value { font-size: 20px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }

/* Filter */
.filter-bar { display: flex; gap: 6px; margin-bottom: 12px; align-items: center; }
.filter-btn { padding: 5px 14px; border: 1px solid var(--border); border-radius: 5px; background: var(--card); color: var(--muted); cursor: pointer; font-family: inherit; font-size: 12px; transition: all 0.2s; }
.filter-btn:hover { border-color: var(--border-light); color: var(--text); }
.filter-btn.active { border-color: var(--green); color: var(--green); background: rgba(0,230,118,0.06); }

/* P&L Cards */
.pnl-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 8px; margin-bottom: 12px; }
.pnl-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px 14px; display: flex; align-items: center; gap: 10px; transition: all 0.2s; }
.pnl-card:hover { border-color: var(--border-light); }
.pnl-card.win { border-left: 3px solid var(--green); }
.pnl-card.loss { border-left: 3px solid var(--red); }
.pnl-rank { font-size: 18px; font-weight: 900; font-family: 'JetBrains Mono', monospace; min-width: 24px; color: var(--muted); text-align: center; }
.pnl-rank.top1 { color: var(--amber); font-size: 22px; }
.pnl-rank.top2 { color: #b0bec5; font-size: 20px; }
.pnl-rank.top3 { color: #a1887f; font-size: 18px; }
.pnl-info { flex: 1; overflow: hidden; }
.pnl-name { font-weight: 700; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pnl-cat { font-size: 11px; color: var(--muted); }
.pnl-nums { text-align: right; flex-shrink: 0; }
.pnl-value { font-size: 15px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
.pnl-pct { font-size: 12px; font-family: 'JetBrains Mono', monospace; }

/* Section title */
.section-title { font-size: 13px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 2px; margin: 16px 0 10px; padding-left: 8px; border-left: 2px solid var(--green); }

/* Table */
.table-wrap { overflow-x: auto; max-height: 500px; overflow-y: auto; border: 1px solid var(--border); border-radius: var(--radius); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead { position: sticky; top: 0; z-index: 1; }
th { padding: 10px 14px; text-align: left; background: var(--card); font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid var(--border); font-family: 'JetBrains Mono', monospace; }
td { padding: 9px 14px; border-bottom: 1px solid rgba(28,40,56,0.3); }
tbody tr:hover td { background: rgba(0,230,118,0.03); }
.addr { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); }

.cat-tag { font-size: 10px; padding: 2px 8px; border-radius: 100px; font-weight: 600; white-space: nowrap; }
.cat-tag.w { background: rgba(0,230,118,0.12); color: var(--green); }
.cat-tag.p { background: rgba(68,138,255,0.12); color: var(--blue); }
.cat-tag.s { background: rgba(255,171,0,0.12); color: var(--amber); }
.cat-tag.t { background: rgba(187,134,252,0.12); color: #bb86fc; }
.cat-tag.c { background: rgba(255,61,79,0.12); color: var(--red); }

.btn { padding: 5px 14px; border: 1px solid var(--green); border-radius: 5px; background: rgba(0,230,118,0.08); color: var(--green); cursor: pointer; font-family: inherit; font-size: 12px; transition: all 0.2s; white-space: nowrap; }
.btn:hover { background: rgba(0,230,118,0.18); }
.btn.danger { border-color: var(--red); color: var(--red); background: rgba(255,61,79,0.06); }
.btn.danger:hover { background: rgba(255,61,79,0.15); }
.btn.muted { border-color: var(--muted); color: var(--muted); cursor: default; }

.search-input { width: 100%; max-width: 300px; padding: 7px 12px; background: var(--card); border: 1px solid var(--border); border-radius: 5px; color: var(--text); font-family: 'JetBrains Mono', monospace; font-size: 12px; outline: none; }
.search-input:focus { border-color: var(--green); }
.search-input::placeholder { color: var(--muted); }

/* Trade cards */
.trade-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 10px; }
.trade-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.trade-card-header { padding: 9px 14px; background: rgba(0,0,0,0.25); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.trade-card-name { font-weight: 700; font-size: 12px; }
.trade-card-body { max-height: 170px; overflow-y: auto; padding: 4px 0; }
.trade-row { display: grid; grid-template-columns: 32px 50px 1fr 60px 60px 50px; gap: 4px; padding: 4px 10px; font-size: 11px; align-items: center; border-bottom: 1px solid rgba(28,40,56,0.3); font-family: 'JetBrains Mono', monospace; }
.trade-row:hover { background: rgba(0,230,118,0.03); }
.trade-side { font-weight: 700; text-align: center; padding: 1px 3px; border-radius: 2px; font-size: 9px; }
.trade-side.buy { background: rgba(0,230,118,0.12); color: var(--green); }
.trade-side.sell { background: rgba(255,61,79,0.12); color: var(--red); }
.trade-qty { text-align: right; }
.trade-market { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); font-size: 10px; }
.trade-usd { text-align: right; color: var(--green); font-weight: 600; }
.trade-status { text-align: right; font-size: 9px; padding: 1px 4px; border-radius: 3px; }
.status-filled { color: var(--green); background: rgba(0,230,118,0.08); }
.status-skipped { color: var(--amber); background: rgba(255,171,0,0.08); }
.status-failed { color: var(--red); background: rgba(255,61,79,0.08); }

.empty { text-align: center; padding: 30px; color: var(--muted); font-size: 13px; }
.status-footer { font-size: 11px; padding: 14px 0; text-align: center; color: var(--muted); font-family: 'JetBrains Mono', monospace; }

@media(max-width:700px) {
  body { padding: 10px; }
  .summary-bar { gap: 14px; }
  .summary-value { font-size: 16px; }
  .pnl-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
  .trade-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div id="app">
  <app-header></app-header>
  <summary-bar></summary-bar>
  <div class="tabs">
    <button class="tab active" @click="activeTab='monitor'" :class="{active:activeTab==='monitor'}">📊 监控面板</button>
    <button class="tab" @click="activeTab='wallets'" :class="{active:activeTab==='wallets'}">🔍 钱包管理</button>
    <button class="tab" @click="activeTab='analytics'" :class="{active:activeTab==='analytics'}">📈 分析</button>
  </div>
  <div class="tab-content active" v-show="activeTab==='monitor'">
    <trade-filter @filter="currentFilter=$event"></trade-filter>
    <pnl-card-grid :wallets="sortedPnl" :active-names="activeNames"></pnl-card-grid>
    <div class="section-title">📋 交易明细</div>
    <trade-list :trades="filteredTrades" :active-names="activeNames" @remove="removeWallet"></trade-list>
  </div>
  <div class="tab-content" v-show="activeTab==='wallets'">
    <wallet-table :candidates="candidates" :active-names="activeNames" @add="addWallet" @remove="removeWallet"></wallet-table>
  </div>
  <div class="tab-content" v-show="activeTab==='analytics'">
    <pnl-trend-chart :pnl-data="pnlHistory" :wallets="wallets"></pnl-trend-chart>
    <alert-config-panel></alert-config-panel>
  </div>
  <toast-container ref="toast"></toast-container>
  <div class="status-footer">数据源: SQLite · 自动刷新 (WebSocket)</div>
</div>
<script type="module" src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add static/index.html && git commit -m "feat: add Vue 3 HTML shell with dark theme"
```

---

### Task 17: Vue app entry (`static/app.js`)

**Files:**
- Create: `G:\trade\static\app.js`

- [ ] **Step 1: Write `app.js`**

```javascript
import { createApp, ref, reactive, computed, onMounted, nextTick } from 'vue';
import { useWebSocket } from './composables/useWebSocket.js';

const API = '/api';

const app = createApp({
  setup() {
    const activeTab = ref('monitor');
    const currentFilter = ref('all');
    const wallets = ref([]);
    const trades = ref([]);
    const summary = ref({});
    const pnlHistory = ref([]);
    const connected = ref(false);
    const activeNames = ref(new Set());

    // Load initial state
    async function loadState() {
      try {
        const resp = await fetch(`${API}/state?t=${Date.now()}`);
        if (resp.ok) {
          const data = await resp.json();
          wallets.value = data.wallets || [];
          trades.value = data.trades || [];
          summary.value = data.summary || {};
          activeNames.value = new Set((data.wallets || []).map(w => w.name));
        }
      } catch (e) { console.error('loadState:', e); }
    }

    // Load wallet list (for wallet management tab)
    async function loadWallets() {
      try {
        const resp = await fetch(`${API}/wallets`);
        if (resp.ok) {
          const data = await resp.json();
          // Don't override P&L data from state
          const existingNames = new Set(wallets.value.map(w => w.name));
          for (const w of data) {
            if (!existingNames.has(w.name)) {
              wallets.value.push(w);
            }
          }
        }
      } catch (e) { console.error('loadWallets:', e); }
    }

    // WebSocket
    const { connect } = useWebSocket({
      onMessage(msg) {
        switch (msg.type) {
          case 'pnl_update':
            // Update wallet P&L values from WebSocket push
            for (const update of (msg.wallets || [])) {
              const idx = wallets.value.findIndex(w => w.name === update.name);
              if (idx >= 0) {
                wallets.value[idx] = { ...wallets.value[idx], ...update };
              }
            }
            break;
          case 'new_trade':
            if (msg.trade) trades.value.unshift(msg.trade);
            break;
          case 'alert':
            // Toast will handle via reactive alerts list
            alerts.value.push(msg);
            break;
          case 'wallet_changed':
            loadState();  // Reload full state
            break;
          case 'ping':
            break;
        }
      },
      onOpen() { connected.value = true; loadState(); },
      onClose() { connected.value = false; setTimeout(() => connect(), 3000); }
    });

    const alerts = ref([]);

    // Filtered trades
    const filteredTrades = computed(() => {
      let result = trades.value.filter(t => t.status === 'FILLED');
      if (currentFilter.value === 'today') {
        const today = new Date().toDateString();
        result = result.filter(t => new Date(t.timestamp).toDateString() === today);
      } else if (currentFilter.value === 'week') {
        const d = new Date();
        const weekStart = new Date(d.getFullYear(), d.getMonth(), d.getDate() - d.getDay());
        result = result.filter(t => new Date(t.timestamp) >= weekStart);
      } else if (currentFilter.value === 'month') {
        const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
        result = result.filter(t => new Date(t.timestamp) >= monthStart);
      }
      return result;
    });

    // Sorted P&L
    const sortedPnl = computed(() => {
      return [...wallets.value].sort((a, b) => (b.pnl_pct || 0) - (a.pnl_pct || 0));
    });

    // P&L history for trend chart
    async function loadPnlHistory(walletId, days = 7) {
      try {
        const resp = await fetch(`${API}/wallets/${walletId}/pnl?days=${days}`);
        if (resp.ok) pnlHistory.value = await resp.json();
      } catch (e) { console.error(e); }
    }

    // Wallet management
    async function addWallet(addr, name, cat) {
      try {
        await fetch(`${API}/wallets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ address: addr, name, category: cat })
        });
        await loadState();
      } catch (e) { console.error(e); }
    }

    async function removeWallet(name) {
      const w = wallets.value.find(w => w.name === name);
      if (!w) return;
      try {
        await fetch(`${API}/wallets/${w.id}`, { method: 'DELETE' });
        await loadState();
      } catch (e) { console.error(e); }
    }

    // Candidate wallet pool (26 pre-vetted addresses)
    const candidates = ref([
      {name:'HondaCivic',addr:'0x15ceffed7bf820cd2d90f90ea24ae9909f5cd5fa',cat:'Weather',winRate:'85.7%',profit:'$48K'},
      {name:'ikik111',addr:'0x57ee70867b4e387de9de34fd62bc685aa02a8112',cat:'Weather',winRate:'—',profit:'$50K'},
      {name:'Maskache2',addr:'0x1f66796b45581868376365aef54b51eb84184c8d',cat:'Weather',winRate:'30%',profit:'$27K'},
      {name:'JoeTheMeteorologist',addr:'0x1838cca016850ac7185a9b149fe7d0bd2d6629b4',cat:'Weather',winRate:'—',profit:'$77K'},
      {name:'BeefSlayer',addr:'0x331bf91c132af9d921e1908ca0979363fc47193f',cat:'Weather',winRate:'67%',profit:'$49K'},
      {name:'Varyage',addr:'0xd75d96a23515172778d3281f53c9180b985100c8',cat:'Weather',winRate:'78%',profit:'—'},
      {name:'wokerjoesleeper',addr:'0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f',cat:'Politics',winRate:'81%',profit:'$900K'},
      {name:'Frank0951',addr:'0x40471b34671887546013ceb58740625c2efe7293',cat:'Politics',winRate:'62.8%',profit:'$290K'},
      {name:'cowcat',addr:'0x38e59b36aae31b164200d0cad7c3fe5e0ee795e7',cat:'Politics',winRate:'>88%',profit:'$200K'},
      {name:'ScottyNooo',addr:'0xbacd00c9080a82ded56f504ee8810af732b0ab35',cat:'Politics',winRate:'58.8%',profit:'$1.3M'},
      {name:'HowDareYou',addr:'0x4bbe10ba5b7f6df147c0dae17b46c44a6e562cf3',cat:'Politics',winRate:'100%',profit:'$277K'},
      {name:'ewelmealt',addr:'0x07921379f7b31ef93da634b688b2fe36897db778',cat:'Sports',winRate:'~100%',profit:'$900K'},
      {name:'EFFICIENCYEXPERT',addr:'0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5',cat:'Sports',winRate:'—',profit:'$580K'},
      {name:'middleoftheocean',addr:'0x6c743aafd813475986dcd930f380a1f50901bd4e',cat:'Sports',winRate:'83.1%',profit:'$470K'},
      {name:'synnet',addr:'0x8e0b7ae246205b1ddf79172148a58a3204139e5c',cat:'Sports',winRate:'—',profit:'$290K'},
      {name:'CKW',addr:'0x92672c80d36dcd08172aa1e51dface0f20b70f9a',cat:'Sports',winRate:'—',profit:'—'},
      {name:'GeorgeSmiley',addr:'0x2110ba2a1e18840109482ff4ddc547baeff45850',cat:'Tech',winRate:'76.1%',profit:'—'},
      {name:'Optimus',addr:'0xd5b97d08ec6098407bfbf66c2786ccc9967fe44e',cat:'Tech',winRate:'>60%',profit:'$73K'},
      {name:'BobInvestments',addr:'0x41816fc1ebdfeb33f6356f2655ab499253b3de86',cat:'Tech',winRate:'75%',profit:'—'},
      {name:'DerDon',addr:'0xf797d4d1c038d1eb0593edae0e66bf8e4b2e0bf',cat:'Tech',winRate:'75%',profit:'$38K'},
      {name:'Mujurry',addr:'0x5ecde7348ea5100af4360dd7a6e0a3fb1d420787',cat:'Tech',winRate:'>80%',profit:'$170K'},
      {name:'BigChungus',addr:'0x06dcaa14f57d8a0573f5dc5940565e6de667af59',cat:'Culture',winRate:'73.7%',profit:'—'},
      {name:'TheRedChip',addr:'0xdf6da574f8b0c0ce5e01ddb1c5a49b87993e9c5c',cat:'Culture',winRate:'45%',profit:'$100K'},
      {name:'GUHHH',addr:'0x033dc6e3e3e0a3ae55402576990392ae910aaf05',cat:'Culture',winRate:'77.9%',profit:'—'},
      {name:'BeN',addr:'0x668d85d791049bf0100e557a72c7ed4dc97297d2',cat:'Culture',winRate:'67.3%',profit:'—'},
      {name:'pol76',addr:'0x36e7e560c4d4cf32926906d939a18cf91f8a0b6b',cat:'Culture',winRate:'72.9%',profit:'—'},
    ]);

    onMounted(() => {
      loadState();
      connect();
    });

    return {
      activeTab, currentFilter, wallets, trades, summary,
      filteredTrades, sortedPnl, pnlHistory, connected,
      activeNames, alerts, candidates,
      addWallet, removeWallet, loadPnlHistory,
    };
  }
});

// Mount
app.mount('#app');
```

- [ ] **Step 2: Create composables directory**

```bash
New-Item -ItemType Directory -Force -Path G:\trade\static\composables
```

- [ ] **Step 3: Commit**

```bash
git add static/app.js && git commit -m "feat: add Vue app entry with reactive state and API integration"
```

---

### Task 18: WebSocket composable (`static/composables/useWebSocket.js`)

**Files:**
- Create: `G:\trade\static\composables\useWebSocket.js`

- [ ] **Step 1: Write `useWebSocket.js`**

```javascript
export function useWebSocket({ onMessage, onOpen, onClose }) {
  let ws = null;
  let pingTimer = null;

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws`;

    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('WS connected');
      pingTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) ws.send('pong');
      }, 25000);
      if (onOpen) onOpen();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (onMessage) onMessage(msg);
      } catch (e) { console.error('WS parse:', e); }
    };

    ws.onclose = () => {
      console.log('WS disconnected');
      if (pingTimer) clearInterval(pingTimer);
      if (onClose) onClose();
    };

    ws.onerror = (e) => {
      console.error('WS error:', e);
    };
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }

  return { connect, send };
}
```

- [ ] **Step 2: Commit**

```bash
git add static/composables/useWebSocket.js && git commit -m "feat: add WebSocket composable with auto-reconnect"
```

---

## Phase 6: Frontend Components

### Task 19: AppHeader + SummaryBar components

**Files:**
- Create: `G:\trade\static\components\AppHeader.js`
- Create: `G:\trade\static\components\SummaryBar.js`

- [ ] **Step 1: Write `AppHeader.js`**

```javascript
export default {
  template: `
  <header>
    <h1>◆ Polymarket 跟单监控面板</h1>
    <div class="sub">
      <span><span class="pulse"></span>实时监控中</span>
      <span class="muted" style="font-size:11px;">{{ clock }}</span>
      <span class="muted" style="font-size:11px;">监控中: {{ walletCount }} 个钱包</span>
    </div>
  </header>`,
  props: {
    walletCount: { type: Number, default: 0 },
  },
  data() {
    return { clock: '' };
  },
  mounted() {
    this.updateClock();
    this._timer = setInterval(() => this.updateClock(), 1000);
  },
  beforeUnmount() {
    clearInterval(this._timer);
  },
  methods: {
    updateClock() {
      this.clock = new Date().toLocaleString('zh-CN', { hour12: false });
    }
  }
};
```

- [ ] **Step 2: Write `SummaryBar.js`**

```javascript
export default {
  template: `
  <div class="summary-bar">
    <div class="summary-item"><span class="summary-label">总本金</span><span class="summary-value mono">\${{ fmt(s.total_capital) }}</span></div>
    <div class="summary-item"><span class="summary-label">可用现金</span><span class="summary-value mono">\${{ fmt(s.total_cash) }}</span></div>
    <div class="summary-item"><span class="summary-label">总市值</span><span class="summary-value mono green">\${{ fmt(s.total_value) }}</span></div>
    <div class="summary-item"><span class="summary-label">累计盈亏</span><span class="summary-value mono" :class="pnlClass">\${{ fmtPnl(s.total_pnl) }}</span></div>
    <div class="summary-item"><span class="summary-label">盈亏%</span><span class="summary-value mono" :class="pnlClass">{{ fmtPnlPct(s.total_pnl_pct) }}%</span></div>
    <div class="summary-item"><span class="summary-label">胜率</span><span class="summary-value mono muted" style="font-size:14px;">{{ s.win_rate != null ? s.win_rate + '%' : '—' }}</span></div>
    <div class="summary-item"><span class="summary-label">最后扫描</span><span class="summary-value mono muted" style="font-size:12px;">{{ s.last_scan || '—' }}</span></div>
  </div>`,
  props: {
    s: { type: Object, default: () => ({}) }
  },
  computed: {
    pnlClass() {
      return (this.s.total_pnl || 0) >= 0 ? 'green' : 'red';
    }
  },
  methods: {
    fmt(v) { return (v || 0).toFixed(2); },
    fmtPnl(v) { const n = v || 0; return (n >= 0 ? '+' : '') + n.toFixed(2); },
    fmtPnlPct(v) { const n = v || 0; return (n >= 0 ? '+' : '') + n.toFixed(2); }
  }
};
```

- [ ] **Step 3: Commit**

```bash
git add static/components/AppHeader.js static/components/SummaryBar.js && git commit -m "feat: add AppHeader and SummaryBar Vue components"
```

---

### Task 20: PnlCardGrid + PnlCard components

**Files:**
- Create: `G:\trade\static\components\PnlCardGrid.js`
- Create: `G:\trade\static\components\PnlCard.js`

- [ ] **Step 1: Write `PnlCardGrid.js`**

```javascript
import PnlCard from './PnlCard.js';

export default {
  components: { PnlCard },
  template: `
  <div class="pnl-grid">
    <pnl-card v-for="(w, idx) in wallets" :key="w.id" :wallet="w" :rank="idx+1" />
    <div v-if="wallets.length===0" class="empty" style="grid-column:1/-1;">暂无盈亏数据，等待首次扫描...</div>
  </div>`,
  props: {
    wallets: { type: Array, default: () => [] }
  }
};
```

- [ ] **Step 2: Write `PnlCard.js`**

```javascript
export default {
  template: `
  <div class="pnl-card" :class="cardClass">
    <span class="pnl-rank" :class="rankClass">#{{ rank }}</span>
    <div class="pnl-info">
      <div class="pnl-name">{{ wallet.name }}</div>
      <div class="pnl-cat">{{ catName }} | 现金\${{ (wallet.cash||0).toFixed(0) }}</div>
    </div>
    <div class="pnl-nums">
      <div class="pnl-value">\${{ (wallet.total_value||0).toFixed(2) }}</div>
      <div class="pnl-pct" :class="pnlColor">{{ pnlSign }}{{ (wallet.pnl_pct||0).toFixed(2) }}%</div>
    </div>
  </div>`,
  props: {
    wallet: { type: Object, required: true },
    rank: { type: Number, default: 0 }
  },
  computed: {
    cardClass() { return (this.wallet.pnl_pct||0) > 0.5 ? 'win' : ((this.wallet.pnl_pct||0) < -0.5 ? 'loss' : ''); },
    rankClass() { return this.rank === 1 ? 'top1' : (this.rank === 2 ? 'top2' : (this.rank === 3 ? 'top3' : '')); },
    pnlColor() { return (this.wallet.pnl_pct||0) >= 0 ? 'green' : 'red'; },
    pnlSign() { return (this.wallet.pnl_pct||0) >= 0 ? '+' : ''; },
    catName() {
      const map = {Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'};
      return map[this.wallet.category] || this.wallet.category || '—';
    }
  }
};
```

- [ ] **Step 3: Commit**

```bash
git add static/components/PnlCardGrid.js static/components/PnlCard.js && git commit -m "feat: add PnlCardGrid and PnlCard Vue components"
```

---

### Task 21: TradeFilter + TradeList + TradeCard components

**Files:**
- Create: `G:\trade\static\components\TradeFilter.js`
- Create: `G:\trade\static\components\TradeList.js`
- Create: `G:\trade\static\components\TradeCard.js`

- [ ] **Step 1: Write `TradeFilter.js`**

```javascript
export default {
  template: `
  <div class="filter-bar">
    <button class="filter-btn" :class="{active:active==='all'}" @click="set('all')">全部</button>
    <button class="filter-btn" :class="{active:active==='today'}" @click="set('today')">今日</button>
    <button class="filter-btn" :class="{active:active==='week'}" @click="set('week')">本周</button>
    <button class="filter-btn" :class="{active:active==='month'}" @click="set('month')">本月</button>
  </div>`,
  emits: ['filter'],
  data() { return { active: 'all' }; },
  methods: { set(f) { this.active = f; this.$emit('filter', f); } }
};
```

- [ ] **Step 2: Write `TradeList.js`**

```javascript
import TradeCard from './TradeCard.js';

export default {
  components: { TradeCard },
  template: `
  <div class="trade-grid">
    <trade-card v-for="name in Object.keys(groupedTrades)" :key="name"
      :wallet-name="name" :wallet-cat="cats[name]||'—'" :trades="groupedTrades[name]"
      @remove="$emit('remove', name)" />
    <div v-if="Object.keys(groupedTrades).length===0" class="empty">暂无成交记录，等待新交易...</div>
  </div>`,
  props: {
    trades: { type: Array, default: () => [] },
    wallets: { type: Array, default: () => [] }
  },
  emits: ['remove'],
  computed: {
    groupedTrades() {
      const g = {};
      for (const t of this.trades) {
        const name = t.wallet_name || '?';
        if (!g[name]) g[name] = [];
        if (g[name].length < 8) g[name].push(t);
      }
      return g;
    },
    cats() {
      const c = {};
      for (const w of this.wallets) {
        c[w.name] = w.category;
      }
      return c;
    }
  }
};
```

- [ ] **Step 3: Write `TradeCard.js`**

```javascript
export default {
  template: `
  <div class="trade-card">
    <div class="trade-card-header">
      <span class="trade-card-name">{{ walletName }}</span>
      <span style="display:flex;align-items:center;gap:8px;">
        <span class="cat-tag" :class="catClass">{{ walletCat }}</span>
        <button class="btn danger" @click="$emit('remove')" style="font-size:9px;padding:2px 8px;">✕</button>
      </span>
    </div>
    <div class="trade-card-body">
      <div v-for="t in trades" :key="t.id" class="trade-row">
        <span class="trade-side" :class="(t.side||'').toLowerCase()">{{ t.side==='BUY'?'买':'卖' }}</span>
        <span class="trade-qty">{{ (t.size||0).toFixed(0) }}</span>
        <span class="trade-market">{{ (t.slug||'').slice(0,35) }}</span>
        <span class="trade-usd">\${{ (t.sim_usd||0).toFixed(2) }}</span>
        <span class="trade-slip" :class="(t.slippage||0)<0.01?'green':'red'">{{ t.slippage != null ? '\$'+t.slippage.toFixed(4) : '—' }}</span>
        <span class="trade-status" :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span>
      </div>
    </div>
  </div>`,
  props: {
    walletName: String,
    walletCat: String,
    trades: Array,
    pnl: Object
  },
  emits: ['remove'],
  computed: {
    catClass() {
      const map = {Weather:'w',Politics:'p',Sports:'s',Tech:'t',Culture:'c'};
      return map[this.walletCat] || 'w';
    }
  },
  methods: {
    statusClass(s) {
      if (s==='FILLED') return 'status-filled';
      if (s==='SKIPPED') return 'status-skipped';
      return 'status-failed';
    },
    statusLabel(s) {
      if (s==='FILLED') return '已成交';
      if (s==='SKIPPED'||s==='HISTORICAL') return '已跳过';
      return '失败';
    }
  }
};
```

- [ ] **Step 4: Commit**

```bash
git add static/components/TradeFilter.js static/components/TradeList.js static/components/TradeCard.js && git commit -m "feat: add TradeFilter, TradeList, TradeCard Vue components"
```

---

### Task 22: WalletTable + WalletRow components

**Files:**
- Create: `G:\trade\static\components\WalletTable.js`
- Create: `G:\trade\static\components\WalletRow.js`

- [ ] **Step 1: Write `WalletTable.js`**

```javascript
import WalletRow from './WalletRow.js';

export default {
  components: { WalletRow },
  template: `
  <div>
    <div class="filter-bar" style="margin-bottom:10px;">
      <input class="search-input" v-model="search" placeholder="搜索钱包名称或地址..." @input="filter">
      <button v-for="c in categories" class="filter-btn" :class="{active:catFilter===c}" @click="catFilter=c">{{ c === 'all' ? '全部' : catName(c) }}</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>状态</th><th>钱包</th><th>地址</th><th>类别</th><th>胜率</th><th>盈利</th><th>操作</th></tr>
        </thead>
        <tbody>
          <wallet-row v-for="w in filtered" :key="w.addr" :wallet="w" :monitoring="activeNames.has(w.name)" @add="addWallet" @remove="removeWallet" />
          <tr v-if="filtered.length===0"><td colspan="7"><div class="empty">无匹配结果</div></td></tr>
        </tbody>
      </table>
    </div>
  </div>`,
  props: {
    candidates: { type: Array, default: () => [] },
    activeNames: { type: Set, default: () => new Set() }
  },
  emits: ['add', 'remove'],
  data() {
    return { search: '', catFilter: 'all', categories: ['all','Weather','Politics','Sports','Tech','Culture'] };
  },
  computed: {
    filtered() {
      let arr = this.candidates;
      if (this.catFilter !== 'all') arr = arr.filter(w => w.cat === this.catFilter);
      const s = this.search.toLowerCase();
      if (s) arr = arr.filter(w => w.name.toLowerCase().includes(s) || w.addr.toLowerCase().includes(s));
      return arr;
    }
  },
  methods: {
    catName(c) { const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[c]||c; },
    addWallet(addr,name,cat) { this.$emit('add', addr, name, cat); },
    removeWallet(name) { this.$emit('remove', name); }
  }
};
```

- [ ] **Step 2: Write `WalletRow.js`**

```javascript
export default {
  template: `
  <tr>
    <td><span v-if="monitoring" style="color:var(--green);font-weight:700;">● 监控中</span><span v-else style="color:var(--muted);">○</span></td>
    <td style="font-weight:600;">{{ wallet.name }}</td>
    <td class="addr" :title="wallet.addr">{{ wallet.addr.slice(0,6) }}...{{ wallet.addr.slice(-4) }}</td>
    <td><span class="cat-tag" :class="catClass">{{ catName }}</span></td>
    <td>{{ wallet.winRate||'—' }}</td>
    <td class="green">{{ wallet.profit||'—' }}</td>
    <td>
      <button v-if="!monitoring" class="btn" @click="$emit('add',wallet.addr,wallet.name,wallet.cat)">+ 添加跟单</button>
      <button v-else class="btn danger" @click="$emit('remove',wallet.name)">移除</button>
    </td>
  </tr>`,
  props: {
    wallet: { type: Object, required: true },
    monitoring: { type: Boolean, default: false }
  },
  emits: ['add', 'remove'],
  computed: {
    catClass() { return (this.wallet.cat||'W')[0].toLowerCase(); },
    catName() { const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[this.wallet.cat]||this.wallet.cat; }
  }
};
```

- [ ] **Step 3: Commit**

```bash
git add static/components/WalletTable.js static/components/WalletRow.js && git commit -m "feat: add WalletTable and WalletRow Vue components"
```

---

### Task 23: PnlTrendChart + AlertConfigPanel components

**Files:**
- Create: `G:\trade\static\components\PnlTrendChart.js`
- Create: `G:\trade\static\components\AlertConfigPanel.js`
- Create: `G:\trade\static\components\ToastContainer.js`

- [ ] **Step 1: Write `PnlTrendChart.js`**

```javascript
import * as echarts from 'echarts';

export default {
  template: `
  <div>
    <div class="filter-bar">
      <select v-model="selectedWallet" @change="loadData" class="search-input" style="max-width:200px;">
        <option value="">选择钱包...</option>
        <option v-for="w in wallets" :key="w.id" :value="w.id">{{ w.name }}</option>
      </select>
      <button class="filter-btn" :class="{active:days===7}" @click="days=7;loadData()">7天</button>
      <button class="filter-btn" :class="{active:days===30}" @click="days=30;loadData()">30天</button>
      <button class="filter-btn" :class="{active:days===90}" @click="days=90;loadData()">90天</button>
    </div>
    <div ref="chart" style="width:100%;height:350px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:12px;"></div>
  </div>`,
  props: {
    wallets: { type: Array, default: () => [] }
  },
  data() {
    return { selectedWallet: '', days: 7, chart: null };
  },
  mounted() {
    this.chart = echarts.init(this.$refs.chart, 'dark');
    window.addEventListener('resize', () => this.chart?.resize());
  },
  methods: {
    async loadData() {
      if (!this.selectedWallet) return;
      const resp = await fetch(`/api/wallets/${this.selectedWallet}/pnl?days=${this.days}`);
      if (!resp.ok) return;
      const data = await resp.json();
      const dates = data.map(d => d.timestamp?.slice(0,10) || '');
      const values = data.map(d => d.pnl || 0);
      this.chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: 50, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#5a6b7d', fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#5a6b7d' }, splitLine: { lineStyle: { color: '#1c2838' } } },
        series: [{
          type: 'line', data: values,
          lineStyle: { color: '#00e676', width: 2 },
          itemStyle: { color: '#00e676' },
          areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[
            {offset:0,color:'rgba(0,230,118,0.15)'},{offset:1,color:'rgba(0,230,118,0)'}
          ])},
          smooth: true
        }]
      }, true);
    }
  }
};
```

- [ ] **Step 2: Write `AlertConfigPanel.js`**

```javascript
export default {
  template: `
  <div class="card" style="padding:14px;margin-bottom:12px;">
    <div class="section-title" style="margin-top:0;">⚙️ 告警配置</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
      <div><label class="muted" style="font-size:11px;">启用告警</label><br>
        <input type="checkbox" v-model="config.enabled" @change="save">
      </div>
      <div><label class="muted" style="font-size:11px;">亏损阈值 (%)</label><br>
        <input class="search-input" type="number" v-model="config.pnl_threshold_pct" @change="save" style="max-width:100px;">
      </div>
      <div><label class="muted" style="font-size:11px;">单笔亏损上限 (\$)</label><br>
        <input class="search-input" type="number" v-model="config.single_loss_usd" @change="save" style="max-width:100px;">
      </div>
      <div><label class="muted" style="font-size:11px;">通知方式</label><br>
        <select v-model="config.webhook_type" @change="save" class="search-input" style="max-width:120px;">
          <option value="">仅仪表盘</option>
          <option value="bark">Bark</option>
          <option value="telegram">Telegram</option>
          <option value="wecom">企业微信</option>
        </select>
      </div>
    </div>
    <div v-if="config.webhook_type" style="margin-top:8px;">
      <label class="muted" style="font-size:11px;">Webhook URL</label><br>
      <input class="search-input" v-model="config.webhook_url" @change="save" style="max-width:100%;" placeholder="https://...">
    </div>
  </div>`,
  data() {
    return { config: { enabled: true, pnl_threshold_pct: -20, single_loss_usd: 10, webhook_type: '', webhook_url: '' } };
  },
  async mounted() {
    try {
      const resp = await fetch('/api/alerts');
      if (resp.ok) this.config = await resp.json();
    } catch (e) {}
  },
  methods: {
    async save() {
      try {
        await fetch('/api/alerts', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.config)
        });
      } catch (e) {}
    }
  }
};
```

- [ ] **Step 3: Write `ToastContainer.js`**

```javascript
export default {
  template: `
  <div style="position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:6px;">
    <div v-for="(t,i) in toasts" :key="i"
      :style="{background:'var(--card)',border:'1px solid '+t.color,padding:'8px 14px',borderRadius:'6px',fontSize:'12px',maxWidth:'320px',transition:'opacity 0.3s'}">
      {{ t.message }}
    </div>
  </div>`,
  props: {
    alerts: { type: Array, default: () => [] }
  },
  data() {
    return { toasts: [] };
  },
  watch: {
    alerts: {
      handler(newAlerts) {
        for (const a of newAlerts) {
          const color = a.type === 'wallet_loss' ? 'var(--red)' : 'var(--amber)';
          this.toasts.push({ message: a.message, color });
          setTimeout(() => this.toasts.shift(), 4000);
        }
      },
      deep: true
    }
  }
};
```

- [ ] **Step 4: Commit**

```bash
git add static/components/PnlTrendChart.js static/components/AlertConfigPanel.js static/components/ToastContainer.js && git commit -m "feat: add PnlTrendChart, AlertConfigPanel, ToastContainer components"
```

---

### Task 24: Wire components in app.js and index.html

**Files:**
- Modify: `G:\trade\static\app.js` (add component imports and registration)
- Modify: `G:\trade\static\index.html` (update template to use components)

- [ ] **Step 1: Update `app.js` — add component registration**

At the top of `app.js`, add imports:

```javascript
import AppHeader from './components/AppHeader.js';
import SummaryBar from './components/SummaryBar.js';
import PnlCardGrid from './components/PnlCardGrid.js';
import TradeFilter from './components/TradeFilter.js';
import TradeList from './components/TradeList.js';
import WalletTable from './components/WalletTable.js';
import PnlTrendChart from './components/PnlTrendChart.js';
import AlertConfigPanel from './components/AlertConfigPanel.js';
import ToastContainer from './components/ToastContainer.js';
```

After `const app = createApp({ ... })`, add:

```javascript
app.component('AppHeader', AppHeader);
app.component('SummaryBar', SummaryBar);
app.component('PnlCardGrid', PnlCardGrid);
app.component('TradeFilter', TradeFilter);
app.component('TradeList', TradeList);
app.component('WalletTable', WalletTable);
app.component('PnlTrendChart', PnlTrendChart);
app.component('AlertConfigPanel', AlertConfigPanel);
app.component('ToastContainer', ToastContainer);
```

- [ ] **Step 2: Update `index.html` template**

Update the `#app` div to use kebab-case component tags and props:

```html
<div id="app">
  <app-header :wallet-count="wallets.length"></app-header>
  <summary-bar :s="summary"></summary-bar>
  <div class="tabs">
    <button class="tab" :class="{active:activeTab==='monitor'}" @click="activeTab='monitor'">📊 监控面板</button>
    <button class="tab" :class="{active:activeTab==='wallets'}" @click="activeTab='wallets'">🔍 钱包管理</button>
    <button class="tab" :class="{active:activeTab==='analytics'}" @click="activeTab='analytics'">📈 分析</button>
  </div>
  <div v-show="activeTab==='monitor'">
    <trade-filter @filter="currentFilter=$event"></trade-filter>
    <pnl-card-grid :wallets="sortedPnl"></pnl-card-grid>
    <div class="section-title">📋 交易明细 ({{ filteredTrades.length }} 笔)</div>
    <trade-list :trades="filteredTrades" :wallets="wallets" @remove="removeWallet"></trade-list>
  </div>
  <div v-show="activeTab==='wallets'">
    <wallet-table :candidates="candidates" :active-names="activeNames" @add="addWallet" @remove="removeWallet"></wallet-table>
  </div>
  <div v-show="activeTab==='analytics'">
    <pnl-trend-chart :wallets="wallets"></pnl-trend-chart>
    <alert-config-panel></alert-config-panel>
  </div>
  <toast-container :alerts="alerts"></toast-container>
  <div class="status-footer">数据源: SQLite · WebSocket 实时推送</div>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add static/app.js static/index.html && git commit -m "feat: wire all Vue components into app"
```

---

## Phase 7: Docker & Deployment

### Task 25: Dockerfile + docker-compose

**Files:**
- Create: `G:\trade\Dockerfile` (overwrite existing)
- Create: `G:\trade\docker-compose.yml` (overwrite existing)
- Create: `G:\trade\.dockerignore`

- [ ] **Step 1: Write `.dockerignore`**

```
__pycache__
*.pyc
*.log
.git
.claude
data/*.db
data/*.db-journal
data/*.db-wal
*.exe
*.png
poly_data
TradingAgents
nohup.out
copy_trader_state.json
wallets_active.json
test_*.py
```

- [ ] **Step 2: Write `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps + Python deps
RUN pip install --no-cache-dir fastapi uvicorn polymarket-paper-trader

# Copy application code (excluding what's in .dockerignore)
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose dashboard port
EXPOSE 8766

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8766/api/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8766"]
```

- [ ] **Step 3: Write `docker-compose.yml`**

```yaml
services:
  copy-trader:
    build: .
    container_name: polymarket-copy-trader
    restart: unless-stopped
    ports:
      - "8766:8766"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
      - SCAN_INTERVAL=120
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

- [ ] **Step 4: Build and verify**

```bash
docker-compose build
```

Expected: Build succeeds without errors.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore && git commit -m "feat: add Docker deployment config"
```

---

## Phase 8: Polish & API Gaps

### Task 26: Add missing API endpoints

**Files:**
- Modify: `G:\trade\api\wallets.py` (add P&L history endpoint)
- Modify: `G:\trade\api\state.py` (add alert config endpoints)

- [ ] **Step 1: Add P&L history to `api/wallets.py`**

```python
@router.get("/{wallet_id}/pnl")
def get_wallet_pnl_history(wallet_id: int, days: int = 7):
    db = get_db()
    rows = db.execute("""
        SELECT * FROM pnl_snapshots
        WHERE wallet_id = ? AND timestamp >= datetime('now', 'localtime', ?)
        ORDER BY timestamp ASC
    """, (wallet_id, f'-{days} days')).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 2: Add alert config endpoints to `api/state.py`**

```python
from models import AlertConfigUpdate

@router.get("/alerts")
def get_alert_config():
    db = get_db()
    row = db.execute("SELECT * FROM alert_config WHERE id = 1").fetchone()
    if not row:
        db.execute("INSERT INTO alert_config (id) VALUES (1)")
        db.commit()
        return {"enabled": 1, "pnl_threshold_pct": -20.0, "single_loss_usd": 10.0, "webhook_type": None, "webhook_url": None}
    return dict(row)

@router.put("/alerts")
def update_alert_config(data: AlertConfigUpdate):
    db = get_db()
    from alerts import update_config
    update_config(db, **{k: v for k, v in data.dict().items() if v is not None})
    return {"ok": True}
```

- [ ] **Step 3: Commit**

```bash
git add api/wallets.py api/state.py && git commit -m "feat: add P&L history and alert config API endpoints"
```

---

## Phase 9: Tests

### Task 27: Backend API tests

**Files:**
- Create: `G:\trade\tests\__init__.py`
- Modify: `G:\trade\tests\test_api.py` (complete with all endpoint tests)

- [ ] **Step 1: Write complete `tests/test_api.py`**

```python
"""API endpoint tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient

# Use test DB, disable scanner
os.environ["DB_PATH"] = ":memory:"
os.environ["SCAN_ENABLED"] = "0"

from main import app
from database import init_db

client = TestClient(app)
init_db()

def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_list_wallets():
    resp = client.get("/api/wallets")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_add_and_remove_wallet():
    addr = "0xdead000000000000000000000000000000000001"
    # Add
    resp = client.post("/api/wallets", json={
        "address": addr, "name": "TestBot", "category": "Weather"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    wallet_id = data["id"]

    # List includes it
    wallets = client.get("/api/wallets").json()
    assert any(w["name"] == "TestBot" for w in wallets)

    # Remove
    resp = client.delete(f"/api/wallets/{wallet_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "TestBot"

    # Reactivate on re-add
    resp = client.post("/api/wallets", json={
        "address": addr, "name": "TestBot", "category": "Weather"
    })
    assert resp.json().get("reactivated") is True

def test_list_trades():
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data
    assert "total" in data

def test_get_summary():
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_capital" in data
    assert "total_pnl" in data

def test_get_state():
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "wallets" in data
    assert "trades" in data
    assert "summary" in data

def test_alert_config():
    resp = client.get("/api/alerts")
    assert resp.status_code == 200

    resp = client.put("/api/alerts", json={"pnl_threshold_pct": -15.0})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
```

- [ ] **Step 2: Run all API tests**

```bash
python -m pytest tests/test_api.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/__init__.py tests/test_api.py && git commit -m "test: add complete API endpoint tests"
```

---

### Task 28: Scanner unit tests

**Files:**
- Create: `G:\trade\tests\test_scanner.py`

- [ ] **Step 1: Write `tests/test_scanner.py`**

```python
"""Scanner unit tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = ":memory:"
os.environ["SCAN_ENABLED"] = "0"

from database import init_db, get_db
from scanner import is_txn_seen, log_trade, get_cost_basis

def test_is_txn_seen():
    init_db()
    db = get_db()
    # Add a wallet first (FK constraint)
    db.execute("INSERT INTO wallets (id, address, name) VALUES (1, '0xtest', 'Test')")
    db.commit()

    assert not is_txn_seen(db, '0xabc123')

    log_trade(db, 1, txn_hash='0xabc123', side='BUY', size=10, whale_price=0.5,
              sim_usd=2, fill_price=0.51, status='FILLED', slippage=0.01,
              pnl_realized=0, slug='test-market', outcome='Yes', timestamp='2026-01-01')

    assert is_txn_seen(db, '0xabc123')

def test_get_cost_basis():
    init_db()
    db = get_db()
    db.execute("DELETE FROM wallets");
    db.execute("INSERT INTO wallets (id, address, name) VALUES (1, '0xtest2', 'Test2')")
    db.commit()

    log_trade(db, 1, txn_hash='0xbuy1', side='BUY', size=100, whale_price=0.5,
              sim_usd=10, fill_price=0.55, status='FILLED', slippage=0,
              pnl_realized=0, slug='my-market', outcome='Yes', timestamp='2026-01-01')

    cost, shares = get_cost_basis(db, 1, 'my-market')
    assert cost == 0.55
    assert shares == 100

    cost, shares = get_cost_basis(db, 1, 'nonexistent')
    assert cost == 0
```

- [ ] **Step 2: Run scanner tests**

```bash
python -m pytest tests/test_scanner.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scanner.py && git commit -m "test: add scanner unit tests"
```

---

## Phase 10: Integration & Cleanup

### Task 29: Full integration test

- [ ] **Step 1: Start server**

```bash
python main.py
```

- [ ] **Step 2: Verify endpoints manually**

```bash
curl http://localhost:8766/api/health
curl http://localhost:8766/api/state
curl http://localhost:8766/api/wallets
curl http://localhost:8766/api/summary
```

- [ ] **Step 3: Verify dashboard loads**

Open http://localhost:8766 in browser. Verify:
- Dark theme renders
- Three tabs work
- Summary bar shows data (even if zeros)
- P&L cards show seeded wallets

- [ ] **Step 4: Verify WebSocket**

Open browser DevTools → Network → WS. Connect to `ws://localhost:8766/ws`. Verify messages arrive.

- [ ] **Step 5: Stop server (Ctrl+C) and commit**

```bash
git add . && git commit -m "chore: integration verification"
```

---

### Task 30: Final cleanup

**Files:**
- Modify: `G:\trade\.gitignore` (add new entries if needed)

- [ ] **Step 1: Update `.gitignore`**

Ensure these entries exist:
```
__pycache__/
*.pyc
*.log
data/*.db
data/*.db-journal
data/*.db-wal
.claude/
tests/__pycache__/
```

- [ ] **Step 2: Archive old files**

Move old files to a reference directory (don't delete — they contain the original pm-trader logic):

```bash
mkdir -p G:\trade\_archive
Move-Item -Force G:\trade\copy_trader.py G:\trade\_archive\
Move-Item -Force G:\trade\copy_dashboard.html G:\trade\_archive\
Move-Item -Force G:\trade\copy_trader_state.json G:\trade\_archive\ 2>$null
Move-Item -Force G:\trade\wallets_active.json G:\trade\_archive\ 2>$null
```

- [ ] **Step 3: Final commit**

```bash
git add .gitignore _archive/ && git commit -m "chore: archive old files, update gitignore"
```

---

## Implementation Order

```
Phase 1 (Foundations): Task 1 → Task 2 → Task 3
Phase 2 (Core Logic):  Task 4 → Task 5
Phase 3 (API Layer):   Task 6 → Task 7 → Task 8 → Task 9 → Task 10 → Task 11
Phase 4 (WebSocket + Alerts): Task 12 → Task 13
Phase 5 (Main App):    Task 14 → Task 15
Phase 6 (Frontend):    Task 16 → Task 17 → Task 18 → Task 19 → Task 20 → Task 21 → Task 22 → Task 23 → Task 24
Phase 7 (Docker):      Task 25
Phase 8 (Polish):      Task 26
Phase 9 (Tests):       Task 27 → Task 28
Phase 10 (Integration): Task 29 → Task 30
```

Each phase is independently testable. Frontend development (Phase 6) can start after Phase 5 (API online).
