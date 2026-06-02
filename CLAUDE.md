# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Polymarket copy-trading bot — monitors target wallets via the Polymarket Data API, paper-trades their moves through `pm-trader` CLI, and serves a real-time dashboard for P&L tracking. The long-term goal is stable Docker deployment on a NAS.

## Key Commands

```bash
# Run the monitor (dashboard at http://localhost:8766/copy_dashboard.html)
python copy_trader.py                          # continuous mode, scan every 120s
python copy_trader.py --interval 300           # custom interval (seconds)
python copy_trader.py --once                   # single scan then exit
python copy_trader.py --dry                    # dry-run (fetch but don't trade)

# Initialize accounts & P&L snapshot
python init_pnl.py

# Close all copy-trading positions
python close_all.py                            # close all wallets
python close_all.py --dry                      # dry-run, show positions only
python close_all.py --list                     # list all open positions
python close_all.py cowcat                     # close specific wallet

# Run the Yahoo Finance proxy (for TradingAgents workbench)
python proxy_server.py                         # port 8765

# Analyze wallet rankings
python poly_analyzer.py --top 20               # export top 20 to wallets_active.json
python quick_top20.py                          # fast ranking via Data API

# Tests
python test_copy_trader.py                     # unit tests for copy_trader pipeline
python test_dashboard.py                       # Playwright E2E dashboard tests (needs monitor running)
python test_consistency.py                     # 60s stability test (no wallet flip detection)

# Docker
docker-compose up -d                           # start the copy-trader service
docker-compose logs -f                         # follow logs
```

## Architecture

### Data Flow
```
Polymarket Data API (public) ──→ copy_trader.py ──→ pm-trader CLI (paper trading)
                                        │
                                        ├── copy_trader_state.json (persisted state, atomic writes)
                                        ├── wallets_active.json (editable wallet config)
                                        └── HTTP :8766 ──→ copy_dashboard.html (SPA dashboard)
                                                           └── proxy_server.py :8765 (Yahoo Finance proxy)
```

### Core Components

**`copy_trader.py`** — The central application (single file, ~475 lines). Three responsibilities:
1. **Trade fetching**: Polls `https://data-api.polymarket.com/trades?user={addr}` for each wallet
2. **Paper trading**: Routes trades to `pm-trader` CLI subprocess (`pm-trader --account copy-{name} buy/sell ...`). Each wallet gets a `copy-{name}` sub-account with $500 initial capital. Trade sizing = min(whale_notional × 2%, $25). Market orders (not limit) for instant fill.
3. **HTTP server**: Embedded `HTTPServer` on port 8766 serving the dashboard HTML and a `/save_wallets` POST endpoint for dashboard-driven wallet management. CORS-enabled.

State file (`copy_trader_state.json`) is written atomically (temp file + `os.replace`). Contains: `seen_txns` (dedup), `sim_trades` (trade log), `wallet_pnl` (per-wallet P&L refreshed every scan), `last_scan` timestamp.

**`copy_dashboard.html`** — Self-contained SPA (no framework). Three tabs:
- **Monitor**: Summary bar (total capital, cash, deployed, total value, P&L, P&L%), P&L card grid sorted by performance, trade detail cards grouped by wallet with time filters (all/today/week/month). Auto-refreshes every 5s via `fetch('api/state')`.
- **Discover**: 26 pre-vetted candidate wallets across 5 categories (Weather/Politics/Sports/Tech/Culture). Search + filter. Add/remove wallets via localStorage, synced to server via `POST /save_wallets`.
- **PolyData Top20**: Reads `poly_data/processed/wallets_top20.json` for data-driven rankings.

Wallet management flow: Dashboard localStorage → `POST /save_wallets` → `wallets_active.json` → `copy_trader.py` reloads on each scan cycle (no restart needed).

**`proxy_server.py`** — Standalone Yahoo Finance CORS proxy on port 8765. Used by `tradingagents-workbench.html`. Endpoints: `/search?q=`, `/price/{ticker}`, `/health`.

**`poly_analyzer.py`** — Offline wallet analysis. Reads `poly_data/processed/trades.csv` (from the poly_data pipeline), computes copy-trading suitability scores based on volume, market diversity, trade frequency, and buy/sell balance. Exports top N to `wallets_active.json` and `poly_data/processed/wallets_top20.json`.

**`quick_top20.py`** — Lightweight alternative to poly_analyzer. Fetches recent trades for 25 known wallets via the Data API (no on-chain data needed) and ranks by a copy-score heuristic. Runs in ~30 seconds.

### Supporting Scripts
- **`close_all.py`** — Close all positions for copy trading accounts via `pm-trader sell`
- **`init_pnl.py`** — Force-initialize all wallet accounts and snapshot P&L to state file
- **`test_copy_trader.py`** — Unit tests for wallet loading, state persistence, Data API, and pm-trader CLI
- **`test_dashboard.py`** — Playwright E2E tests (requires monitor running on :8766)
- **`test_consistency.py`** — 60-second stability test checking for wallet flip-flopping in the dashboard
- **`start_monitor.py`** — Simple debug launcher to verify imports work

### poly_data/ Subproject
Third-party data pipeline (GPL-3.0, from warproxxx/poly_data) for fetching raw Polymarket on-chain data. Uses UV for package management. Three stages: (1) fetch markets from Gamma API, (2) read OrderFilled events from Polygon chain via JSON-RPC, (3) join orders with market metadata into labeled trades.csv. Not needed for the core copy-trading monitor — only for historical wallet analysis.

### TradingAgents/ Subproject
A separate multi-agent LLM trading analysis framework. Co-located but not directly coupled to the copy-trader. Has its own Docker setup, CLI, and tests.

## Key Design Decisions
- **Single data source**: State JSON is the sole source of truth — refreshed every scan, no stale cache issues
- **Wallet config live-reload**: `copy_trader.py` reloads `wallets_active.json` at the start of each scan cycle — dashboard additions/removals take effect without restart
- **Atomic state writes**: Temp file + `os.replace()` prevents readers from seeing partial/corrupt state
- **Trade dedup**: Uses `transactionHash` from Data API to avoid processing the same trade twice
- **Market orders (not limit)**: Uses FOK market orders for instant fill and real slippage capture, rather than the previous limit-order approach that had drift issues
- **Batch processing**: Processes at most 2 new trades per wallet per scan to avoid over-trading on initial sync
- **Monitor start filter**: On startup, sets `MONITOR_START` to current timestamp — only trades after that point are simulated (historical trades are marked as seen but not executed)
