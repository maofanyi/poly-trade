"""Tests for scanner.py — position sync, error recovery, unit helpers."""
import json
from unittest.mock import patch, MagicMock

import pytest
from scanner import scan_wallet_position_sync, log_trade, get_cost_basis, get_wallet_id
# is_txn_seen removed — dedup now via last_trade_ts comparison in scan_wallet_position_sync
# scan_wallet removed — replaced by scan_wallet_position_sync with position-mirroring model


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
PRICE_OK = {"ok": True, "data": {"YES": 0.52, "NO": 0.48}}
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


class TestScanWalletPositionSync:
    """Position sync: fetch trades, update positions, compute diffs, execute."""

    @pytest.fixture(autouse=True)
    def _clean(self, test_db, seed_wallets):
        """Reset state for seed wallets before each test.

        Clears positions, trade_log and resets paused flag. Commits are
        intentionally avoided here so the SAVEPOINT isolation stays intact
        for tests that never commit. Function bodies that call db.commit()
        (e.g. update_position) will auto-commit these changes.
        """
        for w in seed_wallets:
            test_db.execute("DELETE FROM positions WHERE wallet_id = ?", (w['id'],))
            test_db.execute("DELETE FROM trade_log WHERE wallet_id = ?", (w['id'],))
            test_db.execute("UPDATE wallets SET paused = 0 WHERE id = ?", (w['id'],))

    def test_paused_wallet_returns_zero(self, test_db, seed_wallets):
        """Paused wallet should return 0 with no API calls."""
        w = seed_wallets[0]
        test_db.execute("UPDATE wallets SET paused = 1 WHERE id = ?", (w["id"],))
        test_db.commit()
        with patch("scanner.api_fetch") as mock_api:
            count = scan_wallet_position_sync(test_db, w)
        assert count == 0
        mock_api.assert_not_called()

    def test_api_error_returns_zero(self, test_db, seed_wallets):
        """API error should return 0 gracefully."""
        w = seed_wallets[0]
        with patch("scanner.api_fetch", side_effect=Exception("Network error")):
            count = scan_wallet_position_sync(test_db, w)
        assert count == 0

    def test_empty_trades_returns_zero(self, test_db, seed_wallets):
        """No new trades should return 0."""
        w = seed_wallets[0]
        with patch("scanner.api_fetch", return_value=[]):
            count = scan_wallet_position_sync(test_db, w)
        assert count == 0

    def test_new_trade_updates_position(self, test_db, seed_wallets):
        """A new trade should update the position and return count >= 1."""
        import time
        w = seed_wallets[0]
        now_ts = int(time.time())
        canned = [{"transactionHash": "0xSYNC1", "side": "BUY", "size": 10,
                   "price": 0.52, "timestamp": now_ts, "slug": "sync-slug",
                   "outcome": "Yes", "title": "Test"}]
        with patch("scanner.api_fetch", return_value=canned):
            with patch("trader.subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count = scan_wallet_position_sync(test_db, w)
        assert count >= 1
        # Verify position was created
        row = test_db.execute(
            "SELECT whale_shares FROM positions WHERE wallet_id = ? AND slug = ? AND outcome = ?",
            (w["id"], "sync-slug", "Yes")
        ).fetchone()
        assert row is not None
        assert row["whale_shares"] == 10

    def test_older_trade_is_skipped_via_last_trade_ts(self, test_db, seed_wallets):
        """Trade with timestamp <= last_trade_ts for a position should be skipped."""
        import time
        w = seed_wallets[0]
        now_ts = int(time.time())
        # Pre-seed a position with a known newer timestamp
        newer_ts = str(now_ts)
        older_ts = str(now_ts - 100)
        test_db.execute(
            "INSERT INTO positions (wallet_id, slug, outcome, whale_shares, last_trade_ts) "
            "VALUES (?, ?, ?, ?, ?)",
            (w["id"], "old-slug", "Yes", 50, newer_ts)
        )
        # Try to process an older trade (string comparison should skip it)
        canned = [{"transactionHash": "0xOLD2", "side": "BUY", "size": 10,
                   "price": 0.5, "timestamp": older_ts, "slug": "old-slug",
                   "outcome": "Yes", "title": "Old"}]
        with patch("scanner.api_fetch", return_value=canned):
            count = scan_wallet_position_sync(test_db, w)
        assert count == 0

    def test_per_wallet_error_survives(self, test_db, seed_wallets):
        """Error on one wallet should not prevent other wallets from scanning."""
        import time
        w1, w2 = seed_wallets[0], seed_wallets[1]
        now_ts = int(time.time())
        canned = [{"transactionHash": "0xGOOD2", "side": "BUY", "size": 10,
                   "price": 0.52, "timestamp": now_ts, "slug": "ok-slug2",
                   "outcome": "Yes", "title": "OK"}]

        # w1 fails with a network error
        with patch("scanner.api_fetch", side_effect=Exception("Network error")):
            count1 = scan_wallet_position_sync(test_db, w1)
        assert count1 == 0

        # w2 succeeds independently
        with patch("scanner.api_fetch", return_value=canned):
            with patch("trader.subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count2 = scan_wallet_position_sync(test_db, w2)
        assert count2 >= 1


class TestScannerUnitHelpers:
    """Unit tests for scanner helper functions."""

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
