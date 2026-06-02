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
