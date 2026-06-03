"""Tests for GET /api/summary and related endpoints."""


class TestSummary:
    def test_summary_empty_state(self, test_client, seed_wallets, test_db):
        test_db.execute("DELETE FROM trade_log")
        test_db.execute("DELETE FROM pnl_snapshots")
        test_db.commit()
        resp = test_client.get("/api/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 0
        assert data["win_rate"] is None

    def test_summary_with_trades(self, test_client, seed_wallets, test_db):
        test_db.execute("DELETE FROM trade_log")
        test_db.execute("DELETE FROM pnl_snapshots")
        test_db.commit()
        w = seed_wallets[0]
        test_db.execute(
            "INSERT INTO pnl_snapshots (wallet_id, cash, total_value, pnl, pnl_pct) VALUES (?, 490, 510, 10, 2)",
            (w["id"],)
        )
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, pnl_realized, slug, outcome)
               VALUES (?, '0xWIN', 'SELL', 5, 0.5, 3, 'FILLED', 2.5, 's1', 'Yes')""",
            (w["id"],)
        )
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, pnl_realized, slug, outcome)
               VALUES (?, '0xLOSS', 'SELL', 5, 0.5, 3, 'FILLED', -1.0, 's2', 'No')""",
            (w["id"],)
        )
        test_db.commit()

        resp = test_client.get("/api/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 2
        assert data["win_rate"] == 50.0

    def test_success_rate(self, test_client, seed_wallets, test_db):
        test_db.execute("DELETE FROM trade_log")
        test_db.commit()
        w = seed_wallets[0]
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, skip_reason, slug, outcome)
               VALUES (?, '0x_SR_1', 'BUY', 10, 0.5, 5, 'FILLED', NULL, 's1', 'Yes')""",
            (w["id"],)
        )
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, skip_reason, slug, outcome)
               VALUES (?, '0x_SR_2', 'BUY', 10, 0.5, 0, 'SKIPPED', 'already_holding', 's1', 'Yes')""",
            (w["id"],)
        )
        test_db.commit()

        resp = test_client.get("/api/summary/success-rate")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        tw = next(d for d in data if d["name"] == "TestWallet1")
        assert tw["total"] == 2
        assert tw["filled"] == 1
        assert tw["skipped"] == 1
        assert tw["success_rate"] == 50.0
        assert tw["skip_reasons"]["already_holding"] == 1
