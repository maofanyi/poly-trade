"""Tests for GET /api/state."""
import time


class TestGetState:
    def test_returns_expected_structure(self, test_client, seed_wallets, test_db):
        w = seed_wallets[0]
        test_db.execute(
            "INSERT INTO pnl_snapshots (wallet_id, cash, total_value, pnl, pnl_pct) VALUES (?, 500, 520, 20, 4.0)",
            (w["id"],)
        )
        test_db.commit()

        resp = test_client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "wallets" in data
        assert "trades" in data
        assert "summary" in data
        assert "last_scan" in data

    def test_last_scan_none_when_no_scans(self, test_client, seed_wallets):
        resp = test_client.get("/api/state")
        data = resp.json()
        assert data["last_scan"] is None

    def test_last_scan_returns_latest(self, test_client, seed_wallets, test_db):
        test_db.execute(
            "INSERT INTO scan_log (scan_start, scan_end, status) VALUES (?, ?, ?)",
            ("2025-06-01T10:00:00", "2025-06-01T10:01:00", "ok")
        )
        test_db.execute(
            "INSERT INTO scan_log (scan_start, scan_end, status) VALUES (?, ?, ?)",
            ("2025-06-01T10:02:00", "2025-06-01T10:03:00", "ok")
        )
        test_db.commit()

        resp = test_client.get("/api/state")
        data = resp.json()
        assert data["last_scan"] == "2025-06-01T10:03:00"

    def test_trades_limited_to_100(self, test_client, seed_wallets, test_db):
        w = seed_wallets[0]
        for i in range(150):
            test_db.execute(
                """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
                   VALUES (?, ?, 'BUY', 10, 0.5, 5, 'FILLED', ?, 'Yes')""",
                (w["id"], f"0xTRADE_{i}", f"slug-{i}")
            )
        test_db.commit()

        resp = test_client.get("/api/state")
        data = resp.json()
        assert len(data["trades"]) == 100

    def test_total_trades_in_summary(self, test_client, seed_wallets, test_db):
        # Count existing trades as baseline (earlier tests may leak committed data)
        existing = test_db.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]

        w = seed_wallets[0]
        for i in range(5):
            test_db.execute(
                """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
                   VALUES (?, ?, 'BUY', 10, 0.5, 5, 'FILLED', ?, 'Yes')""",
                (w["id"], f"0xCOUNT_{i}", f"count-{i}")
            )
        test_db.commit()

        resp = test_client.get("/api/state")
        data = resp.json()
        assert data["summary"]["total_trades"] == existing + 5


class TestHealthEndpoint:
    def test_health_returns_ok(self, test_client):
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
