"""Tests for GET /api/trades."""


class TestTradesEndpoint:
    def test_list_all_trades(self, test_client, seed_wallets, test_db):
        test_db.execute("DELETE FROM trade_log")
        test_db.commit()
        w = seed_wallets[0]
        for i in range(3):
            test_db.execute(
                """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
                   VALUES (?, ?, 'BUY', 10, 0.5, 5.0, 'FILLED', ?, 'Yes')""",
                (w["id"], f"0xTRADE_A_{i}", f"slug-a-{i}")
            )
        test_db.commit()

        resp = test_client.get("/api/trades")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["trades"]) == 3
        assert "wallet_name" in data["trades"][0]

    def test_filter_by_wallet_id(self, test_client, seed_wallets, test_db):
        test_db.execute("DELETE FROM trade_log")
        test_db.commit()
        w1, w2 = seed_wallets[0], seed_wallets[1]
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
               VALUES (?, '0xW1', 'BUY', 10, 0.5, 5, 'FILLED', 's1', 'Yes')""",
            (w1["id"],)
        )
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
               VALUES (?, '0xW2', 'SELL', 5, 0.3, 2, 'FILLED', 's2', 'No')""",
            (w2["id"],)
        )
        test_db.commit()

        resp = test_client.get(f"/api/trades?wallet_id={w1['id']}")
        data = resp.json()
        assert data["total"] == 1
        assert data["trades"][0]["txn_hash"] == "0xW1"

    def test_filter_by_status(self, test_client, seed_wallets, test_db):
        test_db.execute("DELETE FROM trade_log")
        test_db.commit()
        w = seed_wallets[0]
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
               VALUES (?, '0xSKIP', 'BUY', 10, 0.5, 0, 'SKIPPED', 's1', 'Yes')""",
            (w["id"],)
        )
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
               VALUES (?, '0xFILL', 'BUY', 10, 0.5, 5, 'FILLED', 's2', 'Yes')""",
            (w["id"],)
        )
        test_db.commit()

        resp = test_client.get("/api/trades?status=FILLED")
        data = resp.json()
        assert data["total"] == 1
        assert data["trades"][0]["status"] == "FILLED"

    def test_pagination(self, test_client, seed_wallets, test_db):
        test_db.execute("DELETE FROM trade_log")
        test_db.commit()
        w = seed_wallets[0]
        for i in range(10):
            test_db.execute(
                """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome)
                   VALUES (?, ?, 'BUY', 10, 0.5, 5, 'FILLED', ?, 'Yes')""",
                (w["id"], f"0xPAGE_{i}", f"page-{i}")
            )
        test_db.commit()

        resp = test_client.get("/api/trades?limit=3&offset=0")
        data = resp.json()
        assert len(data["trades"]) == 3
        assert data["total"] == 10
