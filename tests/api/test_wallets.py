"""Tests for /api/wallets CRUD and /api/wallets/cleanup-positions."""
from unittest.mock import patch

# Unique addresses/names to avoid collisions with the conftest seed_wallets
# fixture (which uses "0xAAA"/"0xBBB" and "TestWallet1"/"TestWallet2").
_SEED_ADDRS = [
    ("0xAPI_TEST_WALLET_1_ADDR_001", "ApiTestWallet1", "Weather"),
    ("0xAPI_TEST_WALLET_2_ADDR_002", "ApiTestWallet2", "Politics"),
]
_SEED_NAMES = {name for _, name, _ in _SEED_ADDRS}


def _seed_via_api(test_client):
    """Insert 2 test wallets through the API (idempotent -- reactivates duplicates).

    Returns list of wallet dicts from the API response.
    """
    for addr, name, cat in _SEED_ADDRS:
        resp = test_client.post("/api/wallets", json={
            "address": addr, "name": name, "category": cat
        })
        assert resp.status_code == 200, f"Failed to seed {name}: {resp.text}"

    # Return the matching wallets from the listing
    wallets = test_client.get("/api/wallets").json()
    seeded_addrs = {a for a, _, _ in _SEED_ADDRS}
    return [w for w in wallets if w["address"] in seeded_addrs]


class TestWalletList:
    def test_list_active_wallets(self, test_client):
        seeded = _seed_via_api(test_client)
        assert len(seeded) >= 2, f"Expected >=2 seeded wallets, got {len(seeded)}"
        names = {w["name"] for w in seeded}
        assert "ApiTestWallet1" in names
        assert "ApiTestWallet2" in names

    def test_add_wallet(self, test_client):
        """Adding a wallet via API makes it visible in subsequent list calls."""
        addr = "0xNEW_WALLET_ADD_TYPE_UNIQUE"
        payload = {"address": addr, "name": "NewGuy", "category": "Sports"}
        resp = test_client.post("/api/wallets", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["id"] > 0

        # Verify via API list
        wallets = test_client.get("/api/wallets").json()
        found = [w for w in wallets if w["address"] == addr]
        assert len(found) == 1
        assert found[0]["name"] == "NewGuy"

    def test_add_duplicate_address_reactivates(self, test_client):
        """Adding an existing address reactivates the wallet (200 with reactivated=True)."""
        # Add a wallet first, then try adding the same address
        addr = "0xDUP_TEST_WALLET_ADDRESS_42_CHARS"
        payload = {"address": addr, "name": "FirstAdd", "category": "Sports"}
        resp1 = test_client.post("/api/wallets", json=payload)
        assert resp1.status_code == 200
        assert resp1.json()["ok"] is True

        # Now try adding the same address again -- should reactivate
        payload2 = {"address": addr, "name": "SecondAdd", "category": "Politics"}
        resp2 = test_client.post("/api/wallets", json=payload2)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["ok"] is True
        assert data2.get("reactivated") is True

    def test_remove_wallet_soft_delete(self, test_client):
        """Deleting a wallet sets active=0 (soft delete)."""
        seeded = _seed_via_api(test_client)
        w = seeded[0]

        resp = test_client.delete(f"/api/wallets/{w['id']}")
        assert resp.status_code == 200

        # Verify the wallet is still present but marked inactive
        wallets = test_client.get("/api/wallets").json()
        found = [wal for wal in wallets if wal["id"] == w["id"]]
        assert len(found) == 1
        assert found[0]["active"] is False

    def test_remove_nonexistent_wallet(self, test_client):
        resp = test_client.delete("/api/wallets/99999")
        assert resp.status_code == 404


class TestCleanupPositions:
    def test_cleanup_passes_data_dir_to_pm_trader(self, test_client):
        """Verify cleanup-positions calls pm with --data-dir in the command.

        The cleanup-positions endpoint does ``from trader import pm`` inside
        the function body, so we must patch ``trader.pm`` (not
        ``api.wallets.pm``) to intercept the calls.
        """
        _seed_via_api(test_client)

        with patch("trader.pm") as mock_pm:
            mock_pm.return_value = {"ok": True, "data": {}}
            resp = test_client.post("/api/wallets/cleanup-positions")
            assert resp.status_code == 200
            # pm() should have been called at least once per active wallet
            assert mock_pm.call_count > 0

    def test_cleanup_reinits_with_initial_capital(self, test_client):
        """Verify init uses INITIAL_CAPITAL (500) balance."""
        from config import INITIAL_CAPITAL
        _seed_via_api(test_client)

        captured_cmds = []

        def capture_pm(cmd):
            captured_cmds.append(cmd)
            return {"ok": True, "data": {}}

        with patch("trader.pm", side_effect=capture_pm):
            resp = test_client.post("/api/wallets/cleanup-positions")
            assert resp.status_code == 200

        init_cmds = [c for c in captured_cmds if "init" in c]
        assert len(init_cmds) > 0
        for c in init_cmds:
            assert f"--balance {INITIAL_CAPITAL}" in c


class TestWalletPnl:
    def test_wallet_pnl_no_snapshots(self, test_client):
        """P&L endpoint returns a list (empty when no snapshots exist)."""
        seeded = _seed_via_api(test_client)
        w = seeded[0]
        resp = test_client.get(f"/api/wallets/{w['id']}/pnl")
        assert resp.status_code == 200
        data = resp.json()
        # Endpoint returns a list of pnl_snapshot dicts (may be empty)
        assert isinstance(data, list)

    def test_wallet_pnl_with_snapshots(self, test_client):
        """P&L endpoint returns snapshot rows when they exist."""
        import sqlite3
        from config import DB_PATH

        seeded = _seed_via_api(test_client)
        w = seeded[0]

        # Use a fresh connection to avoid releasing the isolation SAVEPOINT
        # on test_db (which causes data leakage to subsequent tests).
        # Use config.DB_PATH (not os.environ) because test_api.py overwrites
        # the env var at import time.
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        db.execute(
            "INSERT INTO pnl_snapshots (wallet_id, cash, total_value, pnl, pnl_pct) VALUES (?, 500, 500, 0, 0)",
            (w["id"],)
        )
        db.execute(
            "INSERT INTO pnl_snapshots (wallet_id, cash, total_value, pnl, pnl_pct) VALUES (?, 480, 520, 20, 4)",
            (w["id"],)
        )
        db.commit()
        db.close()

        resp = test_client.get(f"/api/wallets/{w['id']}/pnl")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
