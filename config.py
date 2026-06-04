"""Application constants."""
import os

# Polymarket Data API
DATA_API = "https://data-api.polymarket.com"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# pm-trader CLI (data dir persisted in volume to survive container rebuilds)
PM_DATA_DIR = os.environ.get("PM_DATA_DIR", os.path.join(BASE_DIR, "data", "pm-trader"))
PM_TRADER = f"pm-trader --data-dir {PM_DATA_DIR}"

# Trading parameters
INITIAL_CAPITAL = 500.0
MAX_TRADES_PER_SCAN = 2
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", "5"))

DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "trade.db"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Monitor start - set at boot, skip trades before this
MONITOR_START = None

# Default 10 wallets (for seed)
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

# Copy trading — position mirroring (Phase A)
COPY_RATIO = float(os.environ.get("COPY_RATIO", "0.05"))   # 5% of whale notional
MIN_TRADE_USD = 1.00        # Polymarket platform minimum
MAX_PER_MARKET_USD = 25.00  # 5% of $500 capital
MAX_OPEN_POSITIONS = 10     # Concurrent positions cap

# Risk controls
SLIPPAGE_LIMIT = 0.02       # 2% max slippage
PRICE_DEVIATION_LIMIT = 0.10  # 10% from whale entry (position mirroring tolerates more drift than per-trade copying)
DAILY_LOSS_LIMIT = 25.00    # Per wallet daily loss cap
WALLET_LOSS_THRESHOLD = 0.25  # 25% cumulative = pause
CONSECUTIVE_FAILURES = 5    # Pause after N consecutive fails
GLOBAL_LOSS_THRESHOLD = 0.20  # 20% total portfolio loss = halt
