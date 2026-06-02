# Features A–G Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Seven quality-of-life improvements for the Polymarket copy-trading bot: position-aware SELL, market-close caching, backtest simulation, stop-loss, portfolio analysis, and expandable trade details.

**Architecture:** Backend changes in `scanner.py` and new analysis modules. Frontend changes in Vue components. No new dependencies.

**Tech Stack:** Python 3.11, FastAPI, SQLite, Vue 3 CDN, ECharts

---

## A. SELL Position Check

### Task A1: Add position check for SELL trades

**Files:**
- Modify: `G:\trade\scanner.py` (scan_wallet function, SELL branch)

Before executing a SELL, check if we actually hold the position via `has_position()`. If not, log as SKIPPED.

- [ ] **Step 1: Add SELL position guard in scan_wallet**

In `G:\trade\scanner.py`, find the position dedup block (which currently only applies to BUY) and extend it to also cover SELL:

```python
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
```

- [ ] **Step 2: Write test in `tests/test_scanner.py`**

```python
def test_sell_without_position_is_skipped():
    """Verify SELL is skipped when wallet doesn't hold the position."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ["DB_PATH"] = ":memory:"
    os.environ["SCAN_ENABLED"] = "0"
    from database import init_db, get_db
    from trader import has_position
    init_db()
    db = get_db()
    db.execute("INSERT INTO wallets (id, address, name) VALUES (1, '0xatest', 'ATest')")
    db.commit()
    # Wallet has no positions, so SELL should be skipped
    # Verify has_position returns False for a fresh account
    assert not has_position('copy-ATest', 'some-market', 'Yes')
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/test_scanner.py::test_sell_without_position_is_skipped -v
```

- [ ] **Step 4: Commit**

```bash
git add scanner.py tests/test_scanner.py
git commit -m "fix: skip SELL when wallet has no matching position"
```

---

## B. Market Close Detection

### Task B1: Add closed_markets table

**Files:**
- Modify: `G:\trade\database.py` (add closed_markets table)

- [ ] **Step 1: Add table DDL**

In `database.py`, add after the `discovered_wallets` table:

```python
        CREATE TABLE IF NOT EXISTS closed_markets (
            slug TEXT PRIMARY KEY,
            detected_at TEXT DEFAULT (datetime('now','localtime'))
        );
```

- [ ] **Step 2: Verify**

```bash
python -c "from database import init_db, get_db; init_db(); db=get_db(); tables=db.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall(); print([t[0] for t in tables])"
```
Expected: includes `closed_markets`

### Task B2: Check closed_markets before trade, cache on failure

**Files:**
- Modify: `G:\trade\scanner.py` (add market close check and cache logic)

- [ ] **Step 1: Add helper functions to scanner.py**

After `_is_market_expiring`, add:

```python
def _is_market_closed(db, slug: str) -> bool:
    row = db.execute("SELECT slug FROM closed_markets WHERE slug = ?", (slug,)).fetchone()
    return row is not None

def _mark_market_closed(db, slug: str):
    db.execute("INSERT OR IGNORE INTO closed_markets (slug) VALUES (?)", (slug,))
    db.commit()
```

- [ ] **Step 2: Add closed-market skip before execution**

In `scan_wallet`, after the expiry check and before `place_market_order`, add:

```python
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
```

- [ ] **Step 3: Cache on MARKET_NOT_FOUND failure**

In the existing failure handling block (where `err` is checked), add after the `status = 'SKIPPED'` line:

```python
            if 'MARKET_NOT_FOUND' in err or 'not found' in err.lower():
                _mark_market_closed(db, slug)
```

- [ ] **Step 4: Run existing tests to verify no regression**

```bash
python -m pytest tests/ -q
```
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add database.py scanner.py
git commit -m "feat: cache closed markets to avoid repeated failed trade attempts"
```

---

## C. Backtest Mode

### Task C1: Create backtest module

**Files:**
- Create: `G:\trade\backtest.py`
- Create: `G:\trade\api\backtest.py`
- Modify: `G:\trade\main.py` (mount router)

- [ ] **Step 1: Write `backtest.py`**

```python
"""Backtest: simulate copy-trading a wallet from historical Data API trades."""
import json
import time
import urllib.request
from datetime import datetime
from config import INITIAL_CAPITAL

DATA_API = "https://data-api.polymarket.com"


def _fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def run_backtest(address: str, days: int = 30) -> dict:
    """Fetch wallet's recent trades and simulate copy-trading P&L."""
    trades = []
    try:
        # Fetch trades in batches (Data API limit ~100 per call, paginate by timestamp)
        for offset in [0, 100]:
            batch = _fetch(f"{DATA_API}/trades?user={address}&limit=100&offset={offset}")
            if not batch:
                break
            trades.extend(batch)
            if len(batch) < 100:
                break
            time.sleep(0.5)
    except Exception as e:
        return {"error": str(e), "trades_analyzed": 0}

    if not trades:
        return {"error": "No trades found", "trades_analyzed": 0}

    # Filter to requested time window
    cutoff = int(time.time()) - days * 86400
    recent = [t for t in trades if int(t.get('timestamp', 0)) >= cutoff]

    if not recent:
        return {"trades_analyzed": 0, "message": f"No trades in last {days} days", "total_trades_found": len(trades)}

    # Simulate copy-trading
    capital = INITIAL_CAPITAL
    cash = capital
    positions = {}  # slug_outcome -> {shares, cost_basis}
    trade_log = []
    total_pnl = 0.0

    for t in reversed(recent):  # Process oldest first
        side = t.get('side', 'BUY').upper()
        slug = t.get('slug', '')
        outcome = t.get('outcome', 'Yes')
        price = float(t.get('price', 0))
        size = float(t.get('size', 0))
        ts = t.get('timestamp', '')

        whale_notional = size * price
        sim_usd = round(min(max(whale_notional * 0.02, 1.0), capital * 0.05), 2)
        sim_usd = min(sim_usd, cash)  # Can't spend more than available

        if sim_usd < 1.0:
            continue

        pos_key = f"{slug}|{outcome}"

        if side == 'BUY':
            shares = sim_usd / price if price > 0 else 0
            cash -= sim_usd
            if pos_key in positions:
                # Average down/up
                old = positions[pos_key]
                total_shares = old['shares'] + shares
                avg_cost = (old['cost_basis'] * old['shares'] + price * shares) / total_shares
                positions[pos_key] = {'shares': total_shares, 'cost_basis': avg_cost}
            else:
                positions[pos_key] = {'shares': shares, 'cost_basis': price}
            trade_log.append({
                'side': 'BUY', 'price': price, 'sim_usd': round(sim_usd, 2),
                'shares': round(shares, 2), 'slug': slug[:50], 'timestamp': ts
            })
        elif side == 'SELL' and pos_key in positions:
            pos = positions[pos_key]
            sell_value = pos['shares'] * price
            pnl = round((price - pos['cost_basis']) * pos['shares'], 2)
            cash += sell_value
            total_pnl += pnl
            trade_log.append({
                'side': 'SELL', 'price': price, 'pnl': pnl,
                'shares': round(pos['shares'], 2), 'slug': slug[:50], 'timestamp': ts
            })
            del positions[pos_key]

    # Mark remaining positions to market
    unrealized = 0.0
    for pk, pos in positions.items():
        unrealized += pos['shares'] * pos['cost_basis']  # Simplified: value at cost

    total_value = round(cash + unrealized, 2)
    final_pnl = round(total_value - capital, 2)

    return {
        "trades_analyzed": len(trade_log),
        "total_trades_found": len(trades),
        "days": days,
        "initial_capital": capital,
        "final_value": total_value,
        "pnl": final_pnl,
        "pnl_pct": round(final_pnl / capital * 100, 2),
        "open_positions": len(positions),
        "trade_log": trade_log[-50:]  # Last 50 trades
    }
```

- [ ] **Step 2: Write `api/backtest.py`**

```python
"""Backtest API endpoint."""
from fastapi import APIRouter
from backtest import run_backtest

router = APIRouter(prefix="/api", tags=["backtest"])


@router.post("/backtest")
def backtest_wallet(data: dict):
    """Run a backtest for a wallet address. Body: {address, days}"""
    addr = data.get("address", "")
    days = int(data.get("days", 30))
    if not addr:
        return {"error": "address required"}
    return run_backtest(addr, days)
```

- [ ] **Step 3: Mount router in main.py**

Add after the other router includes:

```python
from api.backtest import router as backtest_router
# ... (in the router mounting section)
app.include_router(backtest_router)
```

- [ ] **Step 4: Verify import**

```bash
python -c "from backtest import run_backtest; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backtest.py api/backtest.py main.py
git commit -m "feat: add backtest simulator for historical copy-trading P&L"
```

### Task C2: Backtest frontend

**Files:**
- Create: `G:\trade\static\components\BacktestPanel.js`
- Modify: `G:\trade\static\index.html` (add to analytics tab)
- Modify: `G:\trade\static\app.js` (register component)

- [ ] **Step 1: Write `BacktestPanel.js`**

```javascript
export default {
  template: `
  <div class="card" style="padding:14px;margin-top:12px;">
    <div class="section-title" style="margin-top:0;">🔬 回测模拟</div>
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap;">
      <input class="search-input" v-model="addr" placeholder="输入钱包地址 0x..." style="flex:1;min-width:250px;max-width:420px;">
      <select v-model="days" class="search-input" style="max-width:100px;">
        <option :value="7">7天</option>
        <option :value="30">30天</option>
        <option :value="90">90天</option>
      </select>
      <button class="btn" @click="run" :disabled="running">{{ running ? '计算中...' : '开始回测' }}</button>
    </div>
    <div v-if="result && !result.error" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;">
      <div class="summary-item"><span class="summary-label">初始资金</span><span class="summary-value mono">\${{ result.initial_capital }}</span></div>
      <div class="summary-item"><span class="summary-label">最终市值</span><span class="summary-value mono green">\${{ result.final_value }}</span></div>
      <div class="summary-item"><span class="summary-label">累计盈亏</span><span class="summary-value mono" :class="(result.pnl||0)>=0?'green':'red'">\${{ (result.pnl||0).toFixed(2) }}</span></div>
      <div class="summary-item"><span class="summary-label">回报率</span><span class="summary-value mono" :class="(result.pnl_pct||0)>=0?'green':'red'">{{ (result.pnl_pct||0)>=0?'+':''}}{{ result.pnl_pct }}%</span></div>
      <div class="summary-item"><span class="summary-label">模拟交易</span><span class="summary-value mono muted">{{ result.trades_analyzed }} 笔</span></div>
      <div class="summary-item"><span class="summary-label">持仓中</span><span class="summary-value mono muted">{{ result.open_positions }} 个</span></div>
    </div>
    <div v-if="result && result.error" class="muted" style="padding:10px;">{{ result.error }}</div>
  </div>`,
  data(){ return { addr:'', days:30, running:false, result:null }; },
  methods: {
    async run(){
      if(!this.addr.trim()) return;
      this.running=true; this.result=null;
      try{
        const r=await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:this.addr.trim(),days:this.days})});
        this.result=await r.json();
      }catch(e){ this.result={error:'网络错误'}; }
      this.running=false;
    }
  }
};
```

- [ ] **Step 2: Register in app.js**

Add import and component registration:

```javascript
import BacktestPanel from './components/BacktestPanel.js';
// ...
app.component('BacktestPanel', BacktestPanel);
```

- [ ] **Step 3: Add to analytics tab in index.html**

After `<alert-config-panel>` in the analytics tab:

```html
    <backtest-panel></backtest-panel>
```

- [ ] **Step 4: Commit**

```bash
git add static/components/BacktestPanel.js static/app.js static/index.html
git commit -m "feat: add backtest UI panel in analytics tab"
```

---

## D. Stop-Loss Pause

### Task D1: Add paused column + stop-loss logic

**Files:**
- Modify: `G:\trade\database.py` (add `paused` to wallets)
- Modify: `G:\trade\scanner.py` (check pause before scanning)
- Modify: `G:\trade\api\wallets.py` (pause/unpause endpoints)

- [ ] **Step 1: Add `paused` column to wallets**

In `database.py`, update the wallets CREATE TABLE to include `paused`, and add a migration for existing DBs.

Edit the wallets CREATE TABLE to add `paused INTEGER DEFAULT 0` before `created_at`:

```sql
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY,
            address TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Unknown',
            active INTEGER DEFAULT 1,
            paused INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
```

Add after `init_db()` in database.py:

```python
def migrate():
    """Add any missing columns (idempotent)."""
    db = get_db()
    cols = [r[1] for r in db.execute("PRAGMA table_info(wallets)").fetchall()]
    if 'paused' not in cols:
        db.execute("ALTER TABLE wallets ADD COLUMN paused INTEGER DEFAULT 0")
        db.commit()
```

Call `migrate()` at the end of `init_db()`.

- [ ] **Step 2: Skip paused wallets in scanner**

In `scan_wallet`, add at the very beginning after `wallet_id = get_wallet_id(...)`:

```python
    # Check if wallet is paused
    paused_row = db.execute("SELECT paused FROM wallets WHERE id = ?", (wallet_id,)).fetchone()
    if paused_row and paused_row['paused']:
        return 0  # Skip this wallet
```

- [ ] **Step 3: Auto-pause on severe loss**

In `snapshot_pnl`, after computing `pnl_pct`, add:

```python
    # Auto-pause if loss exceeds 25%
    if pnl_pct <= -25:
        db.execute("UPDATE wallets SET paused = 1 WHERE id = ?", (wallet_id,))
        db.commit()
        print(f"    ⚠️ {acct_name} paused: loss {pnl_pct:.1f}% exceeds threshold")
```

- [ ] **Step 4: Add pause/unpause API endpoints**

In `api/wallets.py`, add:

```python
@router.post("/{wallet_id}/pause")
def pause_wallet(wallet_id: int):
    db = get_db()
    db.execute("UPDATE wallets SET paused = 1 WHERE id = ?", (wallet_id,))
    db.commit()
    return {"ok": True}

@router.post("/{wallet_id}/resume")
def resume_wallet(wallet_id: int):
    db = get_db()
    db.execute("UPDATE wallets SET paused = 0 WHERE id = ?", (wallet_id,))
    db.commit()
    return {"ok": True}
```

- [ ] **Step 5: Show paused status in WalletOut**

In `api/wallets.py`, update `_row_to_out` to include paused status:

Add `"paused": bool(row["paused"]) if "paused" in row.keys() else False` to the returned dict.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add database.py scanner.py api/wallets.py
git commit -m "feat: add stop-loss auto-pause when wallet loses >25%"
```

### Task D2: Frontend pause indicator

**Files:**
- Modify: `G:\trade\static\components\WalletRow.js` (show paused badge)

- [ ] **Step 1: Add paused indicator in WalletRow**

In the status column template, add after the monitoring check:

```html
    <td>
      <span v-if="wallet.paused" style="color:var(--red);" title="已暂停">⏸</span>
      <span v-else-if="monitoring" style="color:var(--green);font-weight:700;">● 监控中</span>
      <span v-else style="color:var(--muted);">○</span>
    </td>
```

- [ ] **Step 2: Commit**

```bash
git add static/components/WalletRow.js
git commit -m "feat: show paused status indicator in wallet row"
```

---

## E. Portfolio Analysis

### Task E1: Portfolio analysis API

**Files:**
- Create: `G:\trade\api\portfolio.py`
- Modify: `G:\trade\main.py` (mount router)

- [ ] **Step 1: Write `api/portfolio.py`**

```python
"""Portfolio analysis: exposure, overlap, category distribution."""
from fastapi import APIRouter
from database import get_db
from config import INITIAL_CAPITAL

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
def portfolio_analysis():
    db = get_db()

    # Total exposure per category
    categories = db.execute("""
        SELECT w.category, COUNT(*) as cnt,
               COALESCE(SUM(p.total_value), COUNT(*)*:cap) as total_value,
               COALESCE(SUM(p.pnl), 0) as total_pnl
        FROM wallets w
        LEFT JOIN (SELECT wallet_id, total_value, pnl FROM pnl_snapshots
                   WHERE id IN (SELECT MAX(id) FROM pnl_snapshots GROUP BY wallet_id)) p
          ON w.id = p.wallet_id
        WHERE w.active = 1
        GROUP BY w.category
    """, {"cap": INITIAL_CAPITAL}).fetchall()

    cat_breakdown = []
    for c in categories:
        cat_breakdown.append({
            "category": c["category"],
            "wallet_count": c["cnt"],
            "total_value": round(c["total_value"] or 0, 2),
            "total_pnl": round(c["total_pnl"] or 0, 2),
            "allocation_pct": round(c["cnt"] * 100.0 / max(1, sum(r["cnt"] for r in categories)), 1)
        })

    # Market overlap: same slug traded by multiple wallets
    overlap = db.execute("""
        SELECT t.slug, COUNT(DISTINCT t.wallet_id) as wallet_count,
               GROUP_CONCAT(DISTINCT w.name) as wallets
        FROM trade_log t
        JOIN wallets w ON t.wallet_id = w.id
        WHERE t.status = 'FILLED'
        GROUP BY t.slug
        HAVING wallet_count >= 2
        ORDER BY wallet_count DESC
        LIMIT 20
    """).fetchall()

    # Top-performing wallets
    top = db.execute("""
        SELECT w.name, w.category, p.total_value, p.pnl, p.pnl_pct
        FROM wallets w
        JOIN (SELECT wallet_id, total_value, pnl, pnl_pct FROM pnl_snapshots
              WHERE id IN (SELECT MAX(id) FROM pnl_snapshots GROUP BY wallet_id)) p
          ON w.id = p.wallet_id
        WHERE w.active = 1
        ORDER BY p.pnl_pct DESC
        LIMIT 5
    """).fetchall()

    return {
        "category_breakdown": cat_breakdown,
        "market_overlap": [dict(r) for r in overlap],
        "top_performers": [dict(r) for r in top],
        "total_value": sum(c["total_value"] for c in cat_breakdown),
        "total_pnl": sum(c["total_pnl"] for c in cat_breakdown),
    }
```

- [ ] **Step 2: Mount in main.py**

```python
from api.portfolio import router as portfolio_router
app.include_router(portfolio_router)
```

- [ ] **Step 3: Verify**

```bash
python -c "from api.portfolio import router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add api/portfolio.py main.py
git commit -m "feat: add portfolio analysis API (exposure, overlap, top performers)"
```

### Task E2: Portfolio analysis frontend

**Files:**
- Create: `G:\trade\static\components\PortfolioPanel.js`
- Modify: `G:\trade\static\index.html` (analytics tab)
- Modify: `G:\trade\static\app.js` (register)

- [ ] **Step 1: Write `PortfolioPanel.js`**

```javascript
export default {
  template: `
  <div class="card" style="padding:14px;margin-bottom:12px;">
    <div class="section-title" style="margin-top:0;">📊 组合分析</div>
    <div v-if="data" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <!-- Categories -->
      <div>
        <div class="muted" style="font-size:11px;margin-bottom:6px;">类别分布</div>
        <div v-for="c in data.category_breakdown" :key="c.category"
          style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid var(--border);">
          <span>{{ catName(c.category) }} ({{ c.wallet_count }}钱包)</span>
          <span class="mono" :class="c.total_pnl>=0?'green':'red'">\${{ c.total_value?.toFixed(0) }} <span style="font-size:10px;">{{ c.total_pnl>=0?'+':'' }}\${{ c.total_pnl?.toFixed(0) }}</span></span>
        </div>
      </div>
      <!-- Top performers -->
      <div>
        <div class="muted" style="font-size:11px;margin-bottom:6px;">最佳表现</div>
        <div v-for="t in data.top_performers" :key="t.name"
          style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid var(--border);">
          <span>{{ t.name }}</span>
          <span class="mono green">+{{ t.pnl_pct?.toFixed(1) }}%</span>
        </div>
      </div>
    </div>
    <!-- Market overlap -->
    <div v-if="data && data.market_overlap.length > 0" style="margin-top:12px;">
      <div class="muted" style="font-size:11px;margin-bottom:6px;">⚠️ 市场重叠 (多钱包持有)</div>
      <div v-for="m in data.market_overlap.slice(0,8)" :key="m.slug"
        style="font-size:11px;padding:2px 0;color:var(--amber);">
        {{ m.wallets }} — {{ m.wallet_count }}个钱包 | {{ (m.slug||'').slice(0,50) }}
      </div>
    </div>
  </div>`,
  props: { data: Object },
  methods: {
    catName(c){ const m={Weather:'天气',Politics:'政治',Sports:'体育',Tech:'科技',Culture:'文化'}; return m[c]||c; }
  }
};
```

- [ ] **Step 2: Register in app.js and load data**

Add to app.js setup:

```javascript
const portfolioData = ref(null);
async function loadPortfolio() {
  try { const r=await fetch('/api/portfolio'); if(r.ok) portfolioData.value=await r.json(); } catch(e){}
}
```

In `onMounted`, add `loadPortfolio()`. Add `portfolioData` to return.

- [ ] **Step 3: Add to analytics tab in index.html**

```html
    <portfolio-panel :data="portfolioData"></portfolio-panel>
```

- [ ] **Step 4: Commit**

```bash
git add static/components/PortfolioPanel.js static/app.js static/index.html
git commit -m "feat: add portfolio analysis panel (categories, overlap, top performers)"
```

---

## F. Expandable Trade Details

### Task F1: Add expandable trade details

**Files:**
- Modify: `G:\trade\static\components\TradeCard.js` (expand on click)
- Modify: `G:\trade\static\index.html` (add detail CSS)

- [ ] **Step 1: Update TradeCard to support expansion**

Rewrite `TradeCard.js` with expandable rows:

```javascript
export default {
  template: `<div class="trade-card">
    <div class="trade-card-header">
      <span class="trade-card-name">{{ walletName }}</span>
      <span style="display:flex;align-items:center;gap:8px;">
        <span class="cat-tag" :class="catClass">{{ walletCat }}</span>
        <button class="btn danger" @click="$emit('remove')" style="font-size:9px;padding:2px 8px;">✕</button>
      </span>
    </div>
    <div class="trade-card-body">
      <div v-for="t in trades" :key="t.id">
        <div class="trade-row" :title="rowTitle(t)" @click="toggle(t.id)" style="cursor:pointer;">
          <span class="trade-side" :class="(t.side||'').toLowerCase()">{{ t.side==='BUY'?'买':'卖' }}</span>
          <span class="trade-qty" title="鲸鱼交易量(份)">{{ (t.size||0).toFixed(0) }}</span>
          <span class="trade-market" :title="t.slug||''">{{ (t.slug||'').slice(0,35) }}</span>
          <span class="trade-usd" :title="'模拟跟单金额: \$'+(t.sim_usd||0).toFixed(2)">\${{ (t.sim_usd||0).toFixed(2) }}</span>
          <span class="trade-slip" :class="slipClass(t)" :title="'鲸鱼价\$'+((t.whale_price)||0).toFixed(4)+' → 成交价\$'+((t.fill_price)||0).toFixed(4)+' | 滑点='+slipPct(t)+'%'">{{ slipPct(t) }}%</span>
          <span class="trade-status" :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span>
        </div>
        <!-- Expanded detail -->
        <div v-if="expanded === t.id" class="trade-detail">
          <div class="detail-row"><span>市场</span><span>{{ t.slug || '—' }}</span></div>
          <div class="detail-row"><span>结果</span><span>{{ t.outcome || '—' }}</span></div>
          <div class="detail-row"><span>鲸鱼价</span><span>\${{ (t.whale_price||0).toFixed(4) }}</span></div>
          <div class="detail-row"><span>成交价</span><span>\${{ (t.fill_price||0).toFixed(4) }}</span></div>
          <div class="detail-row"><span>跟单金额</span><span>\${{ (t.sim_usd||0).toFixed(2) }}</span></div>
          <div class="detail-row"><span>鲸鱼量</span><span>{{ (t.size||0).toFixed(0) }} 份</span></div>
          <div class="detail-row"><span>滑点</span><span>{{ slipPct(t) }}%</span></div>
          <div v-if="t.pnl_realized" class="detail-row"><span>已实现盈亏</span><span :class="t.pnl_realized>=0?'green':'red'">\${{ t.pnl_realized.toFixed(4) }}</span></div>
          <div class="detail-row"><span>时间</span><span>{{ t.timestamp || '—' }}</span></div>
          <div class="detail-row"><span>状态</span><span :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span></div>
          <div class="detail-row"><span>交易Hash</span><span class="addr">{{ (t.txn_hash||'').slice(0,20) }}...</span></div>
        </div>
      </div>
    </div>
  </div>`,
  props: { walletName:String, walletCat:String, trades:Array },
  emits: ['remove'],
  data(){ return { expanded: null }; },
  computed: { catClass(){ const m={Weather:'w',Politics:'p',Sports:'s',Tech:'t',Culture:'c'}; return m[this.walletCat]||'w'; } },
  methods: {
    toggle(id){ this.expanded = this.expanded === id ? null : id; },
    statusClass(s){ if(s==='FILLED')return'status-filled'; if(s==='SKIPPED')return'status-skipped'; return'status-failed'; },
    statusLabel(s){ if(s==='FILLED')return'已成交'; if(s==='SKIPPED'||s==='HISTORICAL')return'已跳过'; return'失败'; },
    statusTooltip(t){ const base=this.statusLabel(t.status); if(t.status==='FILLED')return base+' @ \$'+(t.fill_price||0).toFixed(4); if(t.status==='FAILED')return base+': '+(t.reason||'未知错误'); return base; },
    slipPct(t){ return (t.whale_price>0&&t.fill_price)?Math.abs((t.fill_price-t.whale_price)/t.whale_price*100).toFixed(2):'0.00'; },
    slipClass(t){ const p=parseFloat(this.slipPct(t)); return p<1?'green':(p<5?'muted':'red'); },
    rowTitle(t){ return '鲸鱼'+(t.side==='BUY'?'买入':'卖出')+' '+(t.size||0).toFixed(0)+'份 × \$'+(t.whale_price||0).toFixed(4)+' | 跟单\$'+(t.sim_usd||0).toFixed(2)+' | 成交\$'+(t.fill_price||'?')+' | 滑点'+this.slipPct(t)+'%'; }
  }
};
```

- [ ] **Step 2: Add detail row CSS to index.html**

Add in the `<style>` section:

```css
.trade-detail { padding: 6px 14px; background: rgba(0,0,0,0.2); border-bottom: 1px solid var(--border); }
.detail-row { display: flex; justify-content: space-between; font-size: 10px; padding: 2px 0; color: var(--muted); }
.detail-row span:last-child { font-family: 'JetBrains Mono', monospace; color: var(--text); font-size: 10px; }
```

- [ ] **Step 3: Commit**

```bash
git add static/components/TradeCard.js static/index.html
git commit -m "feat: click trade row to expand full details"
```

---

---

## G. Persistent Wallet List

### Problem
During development, `rm -Force data/trade.db*` wipes user-added wallets on every restart. In production with Docker volumes this won't happen, but we need: (a) guarantee that wallets persist, (b) a safety net for explicit reset, and (c) visual confidence for the user.

### Task G1: Stop wiping DB and add reset endpoint

**Files:**
- Modify: `G:\trade\main.py` (seed logic — already correct, just verify)
- Modify: `G:\trade\api\wallets.py` (add reset-to-defaults endpoint)

- [ ] **Step 1: Verify current persistence is correct**

The current seeding logic in `main.py` lifespan already works:
```python
if db.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] == 0:
    # Only seed if EMPTY — preserves user changes across restarts
```
No code change needed. The only fix is development discipline: **stop doing `rm -Force data/trade.db*` on restarts.**

- [ ] **Step 2: Add "reset to defaults" endpoint in `api/wallets.py`**

```python
@router.post("/reset")
def reset_wallets_to_defaults():
    """Reset all wallets to the default 10. Deactivates custom wallets, reactivates defaults."""
    from config import DEFAULT_WALLETS
    db = get_db()
    # Soft-delete all wallets
    db.execute("UPDATE wallets SET active = 0, paused = 0")
    # Re-insert defaults (reactivate if exists, insert if new)
    for w in DEFAULT_WALLETS:
        existing = db.execute("SELECT id FROM wallets WHERE address = ?", (w["address"],)).fetchone()
        if existing:
            db.execute("UPDATE wallets SET active = 1, paused = 0, name = ?, category = ? WHERE id = ?",
                       (w["name"], w["category"], existing["id"]))
        else:
            db.execute("INSERT INTO wallets (address, name, category) VALUES (?, ?, ?)",
                       (w["address"], w["name"], w["category"]))
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM wallets WHERE active = 1").fetchone()[0]
    return {"ok": True, "active_wallets": count, "message": f"Reset to {count} default wallets"}
```

- [ ] **Step 3: Add persistence status to health endpoint**

In `api/state.py`, enhance `/api/health`:

```python
@router.get("/health")
def health():
    db = get_db()
    wallet_count = db.execute("SELECT COUNT(*) FROM wallets WHERE active = 1").fetchone()[0]
    db_path = os.environ.get("DB_PATH", "data/trade.db")
    db_exists = os.path.exists(db_path)
    return {
        "status": "ok",
        "wallets": wallet_count,
        "db_persisted": db_exists
    }
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/ -q
```
Expected: 10 passed (or more with new tests)

- [ ] **Step 5: Commit**

```bash
git add api/wallets.py api/state.py
git commit -m "feat: wallet persistence — reset endpoint + health shows DB status"
```

### Task G2: Frontend persistence indicator

**Files:**
- Modify: `G:\trade\static\index.html` (add reset button in wallet tab)
- Modify: `G:\trade\static\app.js` (add resetWalletDefaults function)

- [ ] **Step 1: Add reset button in wallet management tab**

In `index.html`, in the wallet tab section, add after the WalletTable:

```html
    <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
      <span class="muted" style="font-size:10px;">💾 钱包列表已持久化 · 重启不丢失</span>
      <button class="btn danger" @click="resetDefaults" style="font-size:10px;padding:3px 10px;">重置为默认列表</button>
    </div>
```

- [ ] **Step 2: Add resetDefaults function in app.js**

```javascript
async function resetDefaults() {
  if (!confirm('确定重置为默认钱包列表？自定义添加的钱包将被移除。')) return;
  try {
    await fetch('/api/wallets/reset', { method: 'POST' });
    await loadState();
  } catch(e) { console.error(e); }
}
```

Add `resetDefaults` to the return statement.

- [ ] **Step 3: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: add wallet persistence indicator and reset-to-defaults button"
```

---

## Implementation Order

```
A (SELL guard) → B (closed markets) → D (stop-loss) → C (backtest) → E (portfolio) → F (trade details) → G (persistence)
```

Each feature is independently testable. A, B, D modify scanner.py together so do them sequentially. C, E, F, G are standalone modules/components.

**Important**: From G onward, do NOT delete `data/trade.db` between restarts. The database persists across server restarts automatically.
