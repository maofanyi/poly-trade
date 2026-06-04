"""Integration tests: full scan pipeline — API fetch → position update → diff → trade execution."""
import json
import time
from unittest.mock import patch, MagicMock


# -- Helpers ------------------------------------------------------------

def _mock_subprocess(responses):
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
BUY_FILLED = {"ok": True, "data": {"trade": {"avg_price": 0.63, "shares": 15}}}

BASE_RESPONSES = {
    "balance": BALANCE_OK,
    "price": PRICE_OK,
    "portfolio": PORTFOLIO_EMPTY,
    "buy": BUY_FILLED,
}


class TestFullScanPipeline:
    """Test the complete position mirroring pipeline."""

    def test_position_update_creates_diffs(self, test_db, seed_wallets):
        """When a whale position is created, a BUY action should be generated and executed."""
        from scanner import update_position, compute_diffs

        w = seed_wallets[0]
        # Simulate whale trade
        trade = {
            'slug': 'live-market-2026', 'outcome': 'Yes', 'side': 'BUY',
            'size': 200, 'price': 0.55, 'timestamp': str(int(time.time())),
            'transactionHash': '0xLIVE1'
        }

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
            update_position(test_db, w['id'], trade)
            actions = compute_diffs(test_db, w['id'], w['name'])

        assert len(actions) > 0, "Should generate BUY action for new whale position"
        assert actions[0]['action'] == 'BUY'
        assert actions[0]['slug'] == 'live-market-2026'
        assert actions[0]['amount'] >= 1.0  # Min trade amount

    def test_closed_market_skipped_in_diffs(self, test_db, seed_wallets):
        """Closed markets should not generate trade actions."""
        from scanner import update_position, compute_diffs

        w = seed_wallets[0]
        # Mark market as closed
        test_db.execute("INSERT INTO closed_markets (slug) VALUES ('dead-market')")
        test_db.commit()

        # Simulate whale trade in closed market
        trade = {
            'slug': 'dead-market', 'outcome': 'Yes', 'side': 'BUY',
            'size': 100, 'price': 0.5, 'timestamp': str(int(time.time())),
            'transactionHash': '0xDEAD1'
        }

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
            update_position(test_db, w['id'], trade)
            actions = compute_diffs(test_db, w['id'], w['name'])

        # Should NOT generate actions for closed market
        dead_actions = [a for a in actions if a['slug'] == 'dead-market']
        assert len(dead_actions) == 0, "Closed market should not generate actions"

    def test_scan_wallet_position_sync_full_flow(self, test_db, seed_wallets):
        """Full scan_wallet_position_sync: API fetch → position update → execute trade."""
        from scanner import scan_wallet_position_sync

        w = seed_wallets[0]
        now = int(time.time())
        canned_trades = [{
            'transactionHash': '0xFULLTEST',
            'side': 'BUY', 'size': 150, 'price': 0.60,
            'timestamp': now, 'slug': 'active-market-test',
            'outcome': 'Yes', 'title': 'Test Market'
        }]

        with patch("scanner.api_fetch", return_value=canned_trades):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count = scan_wallet_position_sync(test_db, w)

        assert count == 1, "Should process 1 new trade"

        # Check that a FILLED trade was logged
        filled = test_db.execute(
            "SELECT * FROM trade_log WHERE wallet_id = ? AND status = 'FILLED'",
            (w['id'],)
        ).fetchone()
        assert filled is not None, "Should have a FILLED trade in the log"
        assert filled['slug'] == 'active-market-test'

    def test_market_not_found_triggers_closed(self, test_db, seed_wallets):
        """When pm-trader returns 'not found', the market should be marked closed."""
        from scanner import scan_wallet_position_sync

        w = seed_wallets[0]
        now = int(time.time())
        canned = [{
            'transactionHash': '0xNOTFOUND',
            'side': 'BUY', 'size': 100, 'price': 0.5,
            'timestamp': now, 'slug': 'expired-market',
            'outcome': 'Yes', 'title': 'Expired'
        }]

        fail_responses = dict(BASE_RESPONSES)
        fail_responses['buy'] = {"ok": False, "error": "MARKET_NOT_FOUND: market does not exist"}

        with patch("scanner.api_fetch", return_value=canned):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(fail_responses)
                count = scan_wallet_position_sync(test_db, w)

        assert count == 1

        # Market should be in closed_markets
        closed = test_db.execute(
            "SELECT slug FROM closed_markets WHERE slug = 'expired-market'"
        ).fetchone()
        assert closed is not None, "Failed market should be auto-closed"

        # Next scan should NOT generate actions for this market
        with patch("scanner.api_fetch", return_value=[]):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = _mock_subprocess(BASE_RESPONSES)
                count = scan_wallet_position_sync(test_db, w)
        assert count == 0  # No new trades, no actions for closed market
