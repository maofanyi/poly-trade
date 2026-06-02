"""API endpoint tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = ":memory:"
os.environ["SCAN_ENABLED"] = "0"

from fastapi.testclient import TestClient
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
    resp = client.post("/api/wallets", json={"address": addr, "name": "TestBot", "category": "Weather"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    wallet_id = data["id"]

    wallets = client.get("/api/wallets").json()
    assert any(w["name"] == "TestBot" for w in wallets)

    resp = client.delete(f"/api/wallets/{wallet_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "TestBot"

    resp = client.post("/api/wallets", json={"address": addr, "name": "TestBot", "category": "Weather"})
    assert resp.json().get("reactivated") is True

def test_list_trades():
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data and "total" in data

def test_get_summary():
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_capital" in data and "total_pnl" in data

def test_get_state():
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "wallets" in data and "trades" in data and "summary" in data

def test_alert_config():
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    resp = client.put("/api/alerts", json={"pnl_threshold_pct": -15.0})
    assert resp.status_code == 200 and resp.json()["ok"] is True

def test_pnl_history():
    resp = client.get("/api/wallets/1/pnl?days=7")
    assert resp.status_code == 200
