"""Tests for alerts.py — config, logging, rate limiting."""
from unittest.mock import patch, MagicMock, AsyncMock


class TestAlertConfig:
    def test_get_config_creates_default(self, test_db):
        from alerts import get_config
        cfg = get_config(test_db)
        assert cfg["enabled"] == 1
        assert cfg["pnl_threshold_pct"] == -20.0
        assert cfg["single_loss_usd"] == 10.0

    def test_update_config(self, test_db):
        from alerts import update_config, get_config
        update_config(test_db, enabled=0, pnl_threshold_pct=-30.0)
        cfg = get_config(test_db)
        assert cfg["enabled"] == 0
        assert cfg["pnl_threshold_pct"] == -30.0

    def test_get_config_idempotent(self, test_db):
        from alerts import get_config
        cfg1 = get_config(test_db)
        cfg2 = get_config(test_db)
        assert cfg1["id"] == cfg2["id"]


class TestAlertLogging:
    def test_log_alert_persists(self, test_db):
        from alerts import log_alert
        log_alert(test_db, "single_trade_loss", 1, "Test message", "toast")
        row = test_db.execute(
            "SELECT * FROM alert_log WHERE alert_type = ?", ("single_trade_loss",)
        ).fetchone()
        assert row is not None
        assert row["message"] == "Test message"

    def test_was_alerted_recently_detects_recent(self, test_db):
        from alerts import log_alert, was_alerted_recently
        log_alert(test_db, "wallet_loss", 1, "Loss alert", "toast")
        assert was_alerted_recently(test_db, "wallet_loss", 1, hours=1) is True

    def test_was_alerted_recently_ignores_old(self, test_db):
        from alerts import was_alerted_recently
        assert was_alerted_recently(test_db, "wallet_loss", 999, hours=1) is False


class TestCheckAlerts:
    def test_no_alert_when_disabled(self, test_db, seed_wallets):
        from alerts import update_config, check_alerts
        update_config(test_db, enabled=0)
        w = seed_wallets[0]

        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, pnl_realized, slug, outcome)
               VALUES (?, '0xLOSS_BIG', 'SELL', 5, 0.5, 3, 'FILLED', -15.0, 's1', 'Yes')""",
            (w["id"],)
        )
        test_db.commit()

        import asyncio
        ws_mock = MagicMock()
        ws_mock.broadcast = AsyncMock()
        asyncio.run(check_alerts(ws_mock, w["name"], w["id"]))
        ws_mock.broadcast.assert_not_called()
