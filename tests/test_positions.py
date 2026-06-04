"""Tests for position model."""
import pytest


class TestUpdatePosition:

    @pytest.fixture(autouse=True)
    def _clean(self, test_db, seed_wallets):
        """Remove positions and trade_log rows for seed wallets before each test.

        The isolation SAVEPOINT is released by db.commit() inside update_position
        and log_trade, so we clean explicitly to prevent cross-test contamination.
        """
        for w in seed_wallets:
            test_db.execute("DELETE FROM positions WHERE wallet_id = ?", (w['id'],))
            test_db.execute("DELETE FROM trade_log WHERE wallet_id = ?", (w['id'],))

    def test_buy_creates_position(self, test_db, seed_wallets):
        from scanner import update_position, get_whale_positions
        w = seed_wallets[0]
        trade = {'slug': 'test-slug', 'outcome': 'Yes', 'side': 'BUY',
                 'size': 100, 'price': 0.5, 'timestamp': '2026-06-04T10:00:00',
                 'transactionHash': '0xTEST'}
        update_position(test_db, w['id'], trade)
        positions = get_whale_positions(test_db, w['id'])
        assert len(positions) == 1
        assert positions[0]['slug'] == 'test-slug'
        assert positions[0]['whale_shares'] == 100

    def test_sell_reduces_position(self, test_db, seed_wallets):
        from scanner import update_position, get_whale_positions
        w = seed_wallets[0]
        update_position(test_db, w['id'],
            {'slug': 'ts', 'outcome': 'Yes', 'side': 'BUY', 'size': 100, 'price': 0.5,
             'timestamp': 't1', 'transactionHash': '0x1'})
        update_position(test_db, w['id'],
            {'slug': 'ts', 'outcome': 'Yes', 'side': 'SELL', 'size': 30, 'price': 0.6,
             'timestamp': 't2', 'transactionHash': '0x2'})
        positions = get_whale_positions(test_db, w['id'])
        assert len(positions) == 1
        assert positions[0]['whale_shares'] == 70

    def test_sell_beyond_zero_clamps(self, test_db, seed_wallets):
        from scanner import update_position
        w = seed_wallets[0]
        update_position(test_db, w['id'],
            {'slug': 'ts', 'outcome': 'No', 'side': 'BUY', 'size': 50, 'price': 0.3,
             'timestamp': 't1', 'transactionHash': '0xA'})
        update_position(test_db, w['id'],
            {'slug': 'ts', 'outcome': 'No', 'side': 'SELL', 'size': 200, 'price': 0.4,
             'timestamp': 't2', 'transactionHash': '0xB'})
        # Position is clamped to 0, so it won't appear in get_whale_positions
        # (which filters whale_shares > 0). Query directly instead.
        row = test_db.execute(
            "SELECT whale_shares FROM positions WHERE wallet_id = ? AND slug = ? AND outcome = ?",
            (w['id'], 'ts', 'No')
        ).fetchone()
        assert row is not None
        assert row['whale_shares'] == 0

    def test_ignores_empty_slug(self, test_db, seed_wallets):
        from scanner import update_position, get_whale_positions
        w = seed_wallets[0]
        update_position(test_db, w['id'],
            {'slug': '', 'outcome': 'Yes', 'side': 'BUY', 'size': 100, 'price': 0.5,
             'timestamp': 't1', 'transactionHash': '0xE'})
        positions = get_whale_positions(test_db, w['id'])
        assert len(positions) == 0
