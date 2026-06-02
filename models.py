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
