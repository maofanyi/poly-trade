"""Tests for diff engine."""
from unittest.mock import patch, MagicMock
import json
import pytest


class TestComputeDiffs:

    @pytest.fixture(autouse=True)
    def _clean(self, test_db, seed_wallets):
        """Remove positions and trade_log rows for seed wallets before each test.

        The isolation SAVEPOINT is released by db.commit() inside update_position,
        so we clean explicitly to prevent cross-test contamination.
        """
        for w in seed_wallets:
            test_db.execute("DELETE FROM positions WHERE wallet_id = ?", (w['id'],))
            test_db.execute("DELETE FROM trade_log WHERE wallet_id = ?", (w['id'],))

    def test_new_whale_position_returns_buy(self, test_db, seed_wallets):
        from scanner import update_position, compute_diffs
        w = seed_wallets[0]
        update_position(test_db, w['id'],
            {'slug': 'new-market', 'outcome': 'Yes', 'side': 'BUY', 'size': 100,
             'price': 0.5, 'timestamp': 't1', 'transactionHash': '0xN'})
        with patch('trader.subprocess.run') as mock_run:
            m = MagicMock()
            m.stdout = json.dumps({"ok": True, "data": []})
            mock_run.return_value = m
            actions = compute_diffs(test_db, w['id'], w['name'])
        buy_actions = [a for a in actions if a['action'] == 'BUY']
        assert len(buy_actions) == 1
        assert buy_actions[0]['slug'] == 'new-market'

    def test_no_whale_position_no_actions(self, test_db, seed_wallets):
        from scanner import compute_diffs
        w = seed_wallets[0]
        with patch('trader.subprocess.run') as mock_run:
            m = MagicMock()
            m.stdout = json.dumps({"ok": True, "data": []})
            mock_run.return_value = m
            actions = compute_diffs(test_db, w['id'], w['name'])
        assert len(actions) == 0
