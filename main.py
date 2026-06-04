"""FastAPI application entry point."""
import asyncio
import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from database import init_db, get_db
from websocket import ws_manager
from scanner import scan_loop, set_ws_manager
from api.wallets import router as wallets_router
from api.trades import router as trades_router
from api.state import router as state_router
from api.summary import router as summary_router
from api.backtest import router as backtest_router
from api.portfolio import router as portfolio_router
from config import STATIC_DIR

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
    # Re-backfill positions from recent trades only (7 days, excluding closed)
    from database import backfill_positions
    old_cnt = db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    db.execute("DELETE FROM positions")
    db.commit()
    backfill_positions()
    new_cnt = db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    print(f"Backfill: cleared {old_cnt} old positions, restored {new_cnt} from last 7 days")
    # Ensure alert_config row exists
    db.execute("INSERT OR IGNORE INTO alert_config (id) VALUES (1)")
    db.commit()

    # Wire WebSocket manager into scanner
    set_ws_manager(ws_manager)

    # Start scanner (skip in test mode)
    if os.environ.get("SCAN_ENABLED", "1") != "0":
        scanner_thread = threading.Thread(target=scan_loop, daemon=True)
        scanner_thread.start()

    # Start maintenance loop (scores 30min + discovery 2h + DB cleanup 4h)
    def maintenance_loop():
        import time as _time
        from scores import refresh_all_scores, discover_wallets
        _time.sleep(30)
        discover_counter = 0
        cleanup_counter = 0
        while True:
            try:
                print("Refreshing wallet scores...")
                refresh_all_scores()
                discover_counter += 1
                cleanup_counter += 1
                if discover_counter >= 4:
                    print("Running wallet discovery scan...")
                    discover_wallets()
                    discover_counter = 0
                if cleanup_counter >= 8:  # Every 4 hours
                    print("Running DB cleanup...")
                    db = get_db()
                    # Delete price_history older than 30 days
                    db.execute("DELETE FROM price_history WHERE recorded_at < datetime('now','-30 days','localtime')")
                    # Keep 1 sample per 4h for data >7 days old
                    db.execute("""
                        DELETE FROM price_history WHERE id NOT IN (
                            SELECT MIN(id) FROM price_history
                            WHERE recorded_at < datetime('now','-7 days','localtime')
                            GROUP BY slug, outcome,
                              strftime('%Y-%m-%d', recorded_at) || '-' ||
                              (CAST(strftime('%H', recorded_at) AS INTEGER) / 4)
                        ) AND recorded_at < datetime('now','-7 days','localtime')
                    """)
                    db.execute("PRAGMA optimize")
                    db.commit()
                    print("  DB cleanup done")
                    cleanup_counter = 0
            except Exception as e:
                print(f"Maintenance error: {e}")
            _time.sleep(1800)
    maint_thread = threading.Thread(target=maintenance_loop, daemon=True)
    maint_thread.start()

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
app.include_router(backtest_router)
app.include_router(portfolio_router)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == 'pong':
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

# Serve static files (Vue dashboard)
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8766, reload=True)
