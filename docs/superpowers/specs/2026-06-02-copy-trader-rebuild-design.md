# Polymarket Copy-Trading Bot — Rebuild Design Spec

**Date**: 2026-06-02  
**Status**: Draft  
**Scope**: Full rebuild of backend (FastAPI) and frontend (Vue 3)

---

## 1. Goal

A Polymarket paper copy-trading application that runs stably in Docker on a NAS. Users monitor P&L of copied wallets via a dashboard and add/remove wallets for simulated copy-trading.

## 2. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend framework | FastAPI | Async, built-in WebSocket, auto API docs |
| Database | SQLite (`sqlite3` stdlib) | Zero-dependency, single-file, ACID, NAS-friendly |
| Trade execution | `pm-trader` CLI wrapper | Reuses existing paper-trading engine |
| Frontend | Vue 3 (CDN, no build step) | Reactive data binding, component model, served as static files by FastAPI |
| Charts | ECharts (CDN) | P&L trend line charts |
| Real-time | FastAPI WebSocket | Replaces 5s polling; pushes P&L updates, new trades, alerts |
| Alerts | In-dashboard toast + webhook | Bark / Telegram Bot / WeCom bot |
| Deployment | Single Docker container | FastAPI serves API + WebSocket + static files |

## 3. Architecture

```
┌────────────── Docker Container ─────────────────┐
│                                                  │
│  FastAPI (single process)                        │
│  ├─ Background thread: scanner loop              │
│  ├─ REST API: /api/*                             │
│  ├─ WebSocket: /ws                               │
│  ├─ Static files: Vue SPA + ECharts              │
│  └─ SQLite: trade_log, wallets, pnl_snapshots    │
│                                                  │
└──────────────────────────────────────────────────┘

Data flow:
  Polymarket Data API ──→ scanner.py ──→ trader.py (pm-trader) ──→ SQLite
                                         │
  SQLite ──→ FastAPI ──→ Vue dashboard (REST + WebSocket)
```

## 4. Backend Module Structure

```
trade/
├── main.py              # FastAPI entry point
├── config.py            # Constants: DATA_API, INITIAL_CAPITAL, etc.
├── database.py          # SQLite init, migrations, connection helper
├── models.py            # Pydantic models (request/response validation)
├── scanner.py           # Trade scan loop (background thread)
├── trader.py            # pm-trader CLI wrapper (buy/sell/balance/close)
├── api/
│   ├── state.py         # GET /api/state (full snapshot)
│   ├── wallets.py       # CRUD /api/wallets
│   ├── trades.py        # GET /api/trades
│   └── summary.py       # GET /api/summary
├── websocket.py         # WebSocket manager (broadcast/unicast/heartbeat)
├── alerts.py            # Alert engine (threshold check + webhook send)
├── static/              # Vue SPA + ECharts (served directly)
│   ├── index.html
│   ├── app.js
│   ├── components/
│   └── lib/
└── tests/
    ├── test_scanner.py
    ├── test_api.py
    └── test_dashboard.py
```

## 5. Database Schema

### wallets

| Column | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| address | TEXT NOT NULL UNIQUE | Ethereum address |
| name | TEXT NOT NULL | Display name |
| category | TEXT | Weather/Politics/Sports/Tech/Culture |
| active | INTEGER DEFAULT 1 | Soft-delete support |
| created_at | TEXT DEFAULT current_timestamp | |

### trade_log

| Column | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| wallet_id | INTEGER FK → wallets.id | |
| txn_hash | TEXT UNIQUE | Dedup key from Data API |
| side | TEXT | BUY / SELL |
| size | REAL | Whale trade size |
| whale_price | REAL | Whale execution price |
| sim_usd | REAL | Simulated USD amount |
| fill_price | REAL | Our fill price |
| status | TEXT | FILLED / SKIPPED / FAILED |
| slippage | REAL | Absolute slippage |
| pnl_realized | REAL | Realized P&L (SELL only) |
| slug | TEXT | Market identifier |
| outcome | TEXT | Yes / No |
| timestamp | TEXT | ISO 8601 |

### pnl_snapshots

| Column | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| wallet_id | INTEGER FK → wallets.id | |
| cash | REAL | Available cash |
| total_value | REAL | Cash + positions |
| pnl | REAL | total_value - INITIAL_CAPITAL (= $500) |
| pnl_pct | REAL | P&L percentage |
| timestamp | TEXT | |

Taken after every scan cycle. Used for trend charts.

### scan_log

| Column | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| scan_start | TEXT | |
| scan_end | TEXT | |
| new_trades_found | INTEGER | |
| status | TEXT | ok / partial_error / fatal |

### alert_config

| Column | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| enabled | INTEGER DEFAULT 1 | |
| pnl_threshold_pct | REAL | e.g. -20.0 |
| single_loss_usd | REAL | e.g. 10.0 |
| webhook_type | TEXT | bark / telegram / wecom |
| webhook_url | TEXT | |
| updated_at | TEXT | |

### alert_log

| Column | Type | Note |
|---|---|---|
| id | INTEGER PK | |
| alert_type | TEXT | wallet_loss / single_trade_loss / scan_error |
| wallet_id | INTEGER FK (nullable) | |
| message | TEXT | |
| sent_via | TEXT | toast / webhook / both |
| created_at | TEXT | |

## 6. API Design

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/state` | Full snapshot for initial dashboard load |
| GET | `/api/wallets` | List all wallets with current P&L |
| POST | `/api/wallets` | Add wallet `{address, name, category}` |
| DELETE | `/api/wallets/{id}` | Remove wallet (soft-delete, set active=0) |
| GET | `/api/wallets/{id}/pnl` | P&L history for trend chart `?days=7` |
| GET | `/api/trades` | Paginated trade list `?wallet_id=&status=&limit=50&offset=0` |
| GET | `/api/summary` | Aggregate: total capital, cash, value, P&L, win rate |
| GET | `/api/alerts` | Alert config + recent alert log |
| PUT | `/api/alerts` | Update alert config |
| GET | `/api/health` | Health check (Docker HEALTHCHECK target) |

### WebSocket `/ws`

Server sends JSON frames with `type` field:

| Type | Payload | When |
|---|---|---|
| `pnl_update` | `{wallets: [{name, pnl, pnl_pct, ...}]}` | After each scan cycle |
| `new_trade` | `{trade: {...}}` | When a trade is executed |
| `scan_start` | `{scan_id, timestamp}` | Scan cycle begins |
| `scan_error` | `{message}` | Scan encounters error |
| `wallet_changed` | `{action: "added"/"removed", wallet}` | Wallet list modified |
| `alert` | `{type, wallet_name, message}` | Alert triggered |

Heartbeat: server sends `ping` every 30s, client replies `pong`.

## 7. Frontend Component Tree

```
App
├─ AppHeader
│   ├─ Title + online indicator (green dot)
│   └─ Clock
├─ SummaryBar
│   ├─ TotalCapital, Cash, Deployed, TotalValue
│   ├─ TotalPnl + PnlPct (colored)
│   └─ LastScan timestamp
├─ TabView
│   ├─ Tab: 监控面板 (Monitor)
│   │   ├─ PnlCardGrid
│   │   │   └─ PnlCard × N
│   │   │       ├─ Rank badge (#1 gold, #2 silver, #3 bronze)
│   │   │       ├─ Wallet name + category tag
│   │   │       └─ Total value + P&L % (green/red)
│   │   ├─ TradeFilter (全部/今日/本周/本月)
│   │   └─ TradeList
│   │       └─ TradeCard × N
│   │           ├─ Wallet name + category
│   │           ├─ Trade rows: side badge, size, market, USD, slippage, status
│   │           └─ Remove (stop copying) button
│   ├─ Tab: 钱包管理 (Wallets)
│   │   ├─ SearchBar (by name or address)
│   │   ├─ CategoryFilter buttons
│   │   └─ WalletTable
│   │       └─ WalletRow × N
│   │           ├─ Status indicator (monitoring / available)
│   │           ├─ Name, address (truncated), category tag
│   │           ├─ Win rate, profit stats
│   │           └─ Add/Remove button
│   └─ Tab: 分析 (Analytics)
│       ├─ WalletSelector (dropdown, which wallet to chart)
│       ├─ PnlTrendChart (ECharts line chart, 7d/30d/90d toggle)
│       ├─ WinRateCard (summary statistics)
│       └─ AlertConfigPanel (thresholds + webhook URL input)
├─ ToastContainer (stacked notifications, top-right)
└─ useWebSocket (global composable)
```

## 8. Vue Component Files

```
static/
├── index.html            # Shell, mounts #app, loads Vue + ECharts CDN
├── app.js                # createApp, register components, mount
├── composables/
│   └── useWebSocket.js   # Connect, reconnect, event dispatch, heartbeat
├── components/
│   ├── AppHeader.js
│   ├── SummaryBar.js
│   ├── PnlCardGrid.js
│   ├── PnlCard.js
│   ├── TradeFilter.js
│   ├── TradeList.js
│   ├── TradeCard.js
│   ├── WalletTable.js
│   ├── WalletRow.js
│   ├── PnlTrendChart.js   # ECharts wrapper
│   ├── AlertConfigPanel.js
│   └── ToastContainer.js
└── lib/
    └── (CDN fallback files if offline)
```

Each component is a plain `.js` file exporting a Vue component options object. Loaded via ES modules (`type="module"`).

## 9. Scanner Logic (preserved from current)

- Poll `https://data-api.polymarket.com/trades?user={addr}&limit=15` for each active wallet
- Dedup via `transactionHash` (stored in `trade_log.txn_hash`)
- Set `MONITOR_START` timestamp at boot; skip trades before it
- Process max 2 new trades per wallet per scan (speed limit)
- Trade sizing: `min(whale_notional × 2%, $25)`, min $1
- Market orders via `pm-trader buy/sell` (FOK for immediate fill)
- Realized P&L for SELL: look up matching BUY trade for same slug → `(sell_price - buy_price) × shares`
- Scan interval: configurable, default 120s
- Each wallet = `copy-{name}` sub-account, $500 initial capital

## 10. Alerts

**Triggers**:
- Wallet total value drops below `pnl_threshold_pct` (default -20%)
- Single trade loss exceeds `single_loss_usd` (default $10)
- Scan cycle fails (connection error, RPC timeout)

**Delivery**:
- Always: WebSocket `alert` event → Vue toast notification
- If configured: POST to webhook URL (Bark/Telegram/WeCom format)

**Rate limiting**: Same alert type for same wallet fires at most once per hour.

## 11. Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn polymarket-paper-trader
COPY . .
EXPOSE 8766
HEALTHCHECK --interval=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8766/api/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8766"]
```

### docker-compose.yml

```yaml
services:
  copy-trader:
    build: .
    container_name: polymarket-copy-trader
    restart: unless-stopped
    ports:
      - "8766:8766"
    volumes:
      - ./data:/app/data          # SQLite DB + backup
    environment:
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Volume mount preserves SQLite database across container recreates. The DB file lives at `data/trade.db` inside the container.

## 12. Migration Path from Old Code

1. **Reuse `trader.py` logic**: Wrap existing `pm()` + `sim_trade()` in the new `trader.py` module
2. **Reuse wallet candidate pool**: Copy 26 addresses from old `copy_dashboard.html` `CANDIDATE_WALLETS` into seed data
3. **Fresh state**: New SQLite schema; old `copy_trader_state.json` can be imported via migration script (optional)
4. **Old files preserved**: Keep `copy_trader.py`, `copy_dashboard.html`, etc. as reference during development; remove after validation

## 13. Testing Strategy

- **Unit tests**: `test_scanner.py` (trade detection, dedup), `test_api.py` (CRUD endpoints, validation)
- **Integration tests**: `test_trader.py` (pm-trader CLI with test account)
- **E2E tests**: Playwright for dashboard (page load, wallet add/remove, P&L card rendering, WebSocket updates)
- **Manual verification**: Start monitor, add a wallet, wait for trades, verify P&L matches pm-trader balance

## 14. Non-Goals (for this phase)

- Real-money trading (paper only)
- Multi-user / authentication
- Mobile app
- Historical backtesting engine
- PolyData on-chain pipeline integration (retain as optional offline analysis tool)
