"""Tests for risk gates."""
from unittest.mock import patch, MagicMock
import json


class TestRiskCheck:
    def test_too_small_trade_skipped(self, test_db, seed_wallets):
        from scanner import risk_check
        passed, reason = risk_check(test_db, 'TestWallet1', 'slug', 'BUY', 0.50, 0.5)
        assert not passed
        assert reason == 'size_too_small'

    def test_normal_trade_passes_basic_checks(self, test_db, seed_wallets):
        from scanner import risk_check
        # Need to mock get_portfolio, get_midpoint since they call pm-trader
        with patch('trader.subprocess.run') as mock_run:
            m = MagicMock()
            m.stdout = json.dumps({"ok": True, "data": []})
            mock_run.return_value = m
            passed, reason = risk_check(test_db, 'TestWallet1', 'some-slug', 'BUY', 5.0, 0.5)
        # Should pass basic checks (not size_too_small at minimum)
        assert reason != 'size_too_small'
