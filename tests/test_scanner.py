"""Tests for scanner.py — trade detection, dedup, skip logic, error recovery."""
import json
import time
from unittest.mock import patch, MagicMock

from scanner import scan_wallet, is_txn_seen, log_trade, get_cost_basis, get_wallet_id


def _mock_subprocess(responses):
    """Return a side_effect function for subprocess.run that matches on command keywords."""
    def side_effect(cmd, shell=True, capture_output=True, text=True, timeout=15):
        for key, result in responses.items():
            if key in cmd:
                m = MagicMock()
                m.stdout = json.dumps(result)
                return m
        m = MagicMock()
        m.stdout = json.dumps({"ok": True, "data": {}})
        return m
    return side_effect


BALANCE_OK = {"ok": True, "data": {"cash": 500, "total_value": 500, "pnl": 0}}
PRICE_OK = {"ok": True, "data": {"YES": 0.62, "NO": 0.38}}
PORTFOLIO_EMPTY = {"ok": True, "data": []}
BUY_FILLED = {"ok": True, "data": {"trade": {"avg_price": 0.5, "shares": 10}}}
SELL_FILLED = {"ok": True, "data": {"trade": {"avg_price": 0.65, "shares": 5}}}

BASE_RESPONSES = {
    "balance": BALANCE_OK,
    "price": PRICE_OK,
    "portfolio": PORTFOLIO_EMPTY,
    "buy": BUY_FILLED,
    "sell": SELL_FILLED,
}


class TestScanWalletDedup:
    """Trade deduplication and MONITOR_START filtering."""

    def test_seen_txn_is_skipped(self, test_db, seed_wallets):
        """Already-seen transaction hash should be skipped without trade execution."""
        w = seed_wallets[0]
        test_db.execute(
            """INSERT INTO trade_log (wallet_id, txn_hash, side, size, whale_price, sim_usd, status, slug, outcome, timestamp)
               VALUES (?, ?, 'BUY', 10, 0.5, 5.0, 'HISTORICAL', 'test-slug', 'Yes', '2025-01-01T00:00:00')""",
            (w["id"], "0xALREADY_SEEN")
        )
        test_db.commit()

        canned = [{"transactionHash": "0xALREADY_SEEN", "side": "BUY", "size": 10,
                    "price": 0.5, "timestamp": int(time.time()), "slug": "test-slug",
                    "outcome": "Yes", "title": "Test"}]
        with patch("scanner.api_fetch", return_value=canned):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count = scan_wallet(test_db, w, ms=0)
        assert count == 0

    def test_historical_trade_marked_seen(self, test_db, seed_wallets):
        """Trades with timestamp before MONITOR_START should be marked HISTORICAL."""
        w = seed_wallets[0]
        old_ts = 1000000000  # well in the past
        now_ts = int(time.time())
        canned = [{"transactionHash": "0xOLD", "side": "BUY", "size": 10,
                    "price": 0.5, "timestamp": old_ts, "slug": "old-slug",
                    "outcome": "Yes", "title": "Old"}]
        with patch("scanner.api_fetch", return_value=canned):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count = scan_wallet(test_db, w, ms=now_ts)
        assert count == 0
        row = test_db.execute(
            "SELECT status FROM trade_log WHERE txn_hash = ?", ("0xOLD",)
        ).fetchone()
        assert row is not None, "Historical trade should have been inserted"
        assert row["status"] == "HISTORICAL"

    def test_new_trade_is_processed(self, test_db, seed_wallets):
        """A fresh trade after MONITOR_START should be processed."""
        w = seed_wallets[0]
        now_ts = int(time.time())
        canned = [{"transactionHash": "0xFRESH", "side": "BUY", "size": 10,
                    "price": 0.5, "timestamp": now_ts, "slug": "fresh-slug",
                    "outcome": "Yes", "title": "Fresh"}]
        with patch("scanner.api_fetch", return_value=canned):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count = scan_wallet(test_db, w, ms=0)
        assert count >= 1

    def test_max_2_trades_per_scan(self, test_db, seed_wallets):
        """Only the last MAX_TRADES_PER_SCAN (2) trades should be processed per scan."""
        w = seed_wallets[0]
        now = int(time.time())
        canned = []
        for i in range(5):
            canned.append({
                "transactionHash": f"0xNEW_{i}", "side": "BUY", "size": 10,
                "price": 0.5, "timestamp": now - i * 60,
                "slug": f"slug-{i}", "outcome": "Yes", "title": f"Test {i}"
            })
        with patch("scanner.api_fetch", return_value=canned):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count = scan_wallet(test_db, w, ms=0)
        assert count <= 2


class TestSkipConditions:
    """Skip logic for already-holding, no-position, expiring, and closed markets."""

    def test_already_holding_skip(self, test_db, seed_wallets):
        """BUY should be skipped when we already hold the same market+outcome."""
        w = seed_wallets[0]
        now = int(time.time())
        canned = [{"transactionHash": "0xHOLDING", "side": "BUY", "size": 10,
                    "price": 0.5, "timestamp": now, "slug": "held-slug",
                    "outcome": "Yes", "title": "Held"}]
        with patch("scanner.api_fetch", return_value=canned):
            with patch("scanner.has_position", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                    count = scan_wallet(test_db, w, ms=0)
        assert count >= 1
        row = test_db.execute(
            "SELECT status, skip_reason FROM trade_log WHERE txn_hash = ?", ("0xHOLDING",)
        ).fetchone()
        assert row is not None, "Skipped trade should be logged"
        assert row["status"] == "SKIPPED"
        assert row["skip_reason"] == "already_holding"

    def test_sell_without_position_skip(self, test_db, seed_wallets):
        """SELL should be skipped when we don't hold the position."""
        w = seed_wallets[0]
        now = int(time.time())
        canned = [{"transactionHash": "0xNOSELL", "side": "SELL", "size": 10,
                    "price": 0.5, "timestamp": now, "slug": "no-pos-slug",
                    "outcome": "Yes", "title": "No Position"}]
        with patch("scanner.api_fetch", return_value=canned):
            with patch("scanner.has_position", return_value=False):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                    count = scan_wallet(test_db, w, ms=0)
        assert count >= 1
        row = test_db.execute(
            "SELECT status, skip_reason FROM trade_log WHERE txn_hash = ?", ("0xNOSELL",)
        ).fetchone()
        assert row is not None, "Skipped SELL should be logged"
        assert row["status"] == "SKIPPED"
        assert row["skip_reason"] == "no_position"


class TestScanErrorRecovery:
    """Per-wallet API errors should not kill the entire scan."""

    def test_api_error_per_wallet_survives(self, test_db, seed_wallets):
        """Error on one wallet should not prevent other wallets from scanning."""
        w1, w2 = seed_wallets[0], seed_wallets[1]
        now = int(time.time())
        canned = [{"transactionHash": "0xGOOD", "side": "BUY", "size": 10,
                    "price": 0.5, "timestamp": now, "slug": "ok-slug",
                    "outcome": "Yes", "title": "OK"}]

        # w1 fails with a network error
        with patch("scanner.api_fetch", side_effect=Exception("Network error")):
            count1 = scan_wallet(test_db, w1, ms=0)
        assert count1 == 0

        # w2 succeeds independently
        with patch("scanner.api_fetch", return_value=canned):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count2 = scan_wallet(test_db, w2, ms=0)
        assert count2 >= 1

    def test_paused_wallet_is_skipped(self, test_db, seed_wallets):
        """A paused wallet should return 0 immediately with no API calls."""
        w = seed_wallets[0]
        test_db.execute("UPDATE wallets SET paused = 1 WHERE name = ?", (w["name"],))
        test_db.commit()

        canned = [{"transactionHash": "0xPAUSED", "side": "BUY", "size": 10,
                    "price": 0.5, "timestamp": int(time.time()), "slug": "paused-slug",
                    "outcome": "Yes", "title": "Paused"}]
        with patch("scanner.api_fetch", return_value=canned) as mock_api:
            count = scan_wallet(test_db, w, ms=0)
        assert count == 0
        mock_api.assert_not_called()


class TestScannerUnitHelpers:
    """Unit tests for scanner helper functions."""

    def test_is_txn_seen_true(self, test_db, seed_wallets):
        """is_txn_seen returns True for an already-logged transaction."""
        w = seed_wallets[0]
        log_trade(test_db, w["id"],
                  txn_hash="0xabc123", side="BUY", size=10, whale_price=0.5,
                  sim_usd=2, fill_price=0.51, status="FILLED", slippage=0.01,
                  pnl_realized=0, slug="test-market", outcome="Yes",
                  timestamp="2026-01-01", skip_reason=None)
        assert is_txn_seen(test_db, "0xabc123")

    def test_is_txn_seen_false(self, test_db, seed_wallets):
        """is_txn_seen returns False for an unknown transaction."""
        assert not is_txn_seen(test_db, "0xnotfound")

    def test_get_cost_basis_found(self, test_db, seed_wallets):
        """get_cost_basis returns the cost and shares of the last BUY."""
        w = seed_wallets[0]
        log_trade(test_db, w["id"],
                  txn_hash="0xbuy1", side="BUY", size=100, whale_price=0.5,
                  sim_usd=10, fill_price=0.55, status="FILLED", slippage=0,
                  pnl_realized=0, slug="my-market", outcome="Yes",
                  timestamp="2026-01-01", skip_reason=None)
        cost, shares = get_cost_basis(test_db, w["id"], "my-market")
        assert cost == 0.55
        assert shares == 100

    def test_get_cost_basis_not_found(self, test_db, seed_wallets):
        """get_cost_basis returns (0, 0) for a slug with no BUY."""
        cost, shares = get_cost_basis(test_db, seed_wallets[0]["id"], "nonexistent")
        assert cost == 0
        assert shares == 0

    def test_get_wallet_id_active(self, test_db, seed_wallets):
        """get_wallet_id returns the id for an active wallet."""
        wid = get_wallet_id(test_db, seed_wallets[0]["name"])
        assert wid is not None
        assert isinstance(wid, int)

    def test_get_wallet_id_inactive(self, test_db, seed_wallets):
        """get_wallet_id returns None for a wallet with active=0."""
        w = seed_wallets[0]
        test_db.execute("UPDATE wallets SET active = 0 WHERE id = ?", (w["id"],))
        test_db.commit()
        wid = get_wallet_id(test_db, w["name"])
        assert wid is None
