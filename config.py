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
