"""Tests for trader.py with subprocess.run mocked out."""
import json
from unittest.mock import patch, MagicMock


def _make_run_side_effect(responses: dict):
    """Build a side_effect for subprocess.run. First key found in cmd wins."""
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


class TestEnsureAccount:
    def test_creates_new_account_when_balance_fails(self):
        responses = {
            "balance": {"ok": False},
            "init": {"ok": True, "data": {"cash": 500, "total_value": 500, "pnl": 0}},
        }
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import ensure_account
            result = ensure_account("copy-Test")

        assert result["cash"] == 500.0
        cmds = [c[0][0] for c in mock_run.call_args_list]
        assert any("balance" in c for c in cmds)
        assert any("init" in c for c in cmds)

    def test_returns_existing_balance(self):
        responses = {
            "balance": {"ok": True, "data": {"cash": 480, "total_value": 520, "pnl": 20}},
        }
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import ensure_account
            result = ensure_account("copy-Test")

        assert result["cash"] == 480
        cmds = [c[0][0] for c in mock_run.call_args_list]
        assert not any("init" in c for c in cmds)


class TestPlaceMarketOrder:
    def test_buy_fills(self):
        responses = {
            "buy": {"ok": True, "data": {"trade": {"avg_price": 0.63, "shares": 15}}},
        }
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import place_market_order
            result = place_market_order("copy-Test", "slug-here", "Yes", "buy", 10.0)

        assert result["ok"] is True
        assert result["data"]["trade"]["avg_price"] == 0.63

    def test_buy_fails_insufficient_balance(self):
        responses = {
            "buy": {"ok": False, "error": "Insufficient balance"},
        }
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import place_market_order
            result = place_market_order("copy-Test", "slug-here", "Yes", "buy", 10000.0)

        assert result["ok"] is False

    def test_sell_fills(self):
        responses = {
            "sell": {"ok": True, "data": {"trade": {"avg_price": 0.35, "shares": 20}}},
        }
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import place_market_order
            result = place_market_order("copy-Test", "slug-here", "No", "sell", 7.0)

        assert result["ok"] is True


class TestGetMidpoint:
    def test_returns_yes_no_prices(self):
        responses = {"price": {"ok": True, "data": {"YES": 0.62, "NO": 0.38}}}
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import get_midpoint
            result = get_midpoint("some-market")
        assert result == {"YES": 0.62, "NO": 0.38}

    def test_returns_none_on_failure(self):
        responses = {"price": {"ok": False}}
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import get_midpoint
            result = get_midpoint("invalid-market")
        assert result is None


class TestGetPortfolio:
    def test_returns_positions(self):
        responses = {"portfolio": {"ok": True, "data": [
            {"market_slug": "will-btc-hit-100k", "outcome": "Yes", "shares": 100},
            {"market_slug": "rain-tomorrow", "outcome": "No", "shares": 50},
        ]}}
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import get_portfolio
            result = get_portfolio("copy-Test")
        assert len(result) == 2
        assert result[0]["slug"] == "will-btc-hit-100k"

    def test_empty_portfolio(self):
        responses = {"portfolio": {"ok": True, "data": []}}
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import get_portfolio
            result = get_portfolio("copy-Test")
        assert result == []


class TestHasPosition:
    def test_finds_existing_slug_outcome(self):
        responses = {"portfolio": {"ok": True, "data": [
            {"market_slug": "market-abc", "outcome": "Yes", "shares": 10}
        ]}}
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import has_position
            assert has_position("copy-Test", "market-abc", "Yes") is True

    def test_misses_different_outcome(self):
        responses = {"portfolio": {"ok": True, "data": [
            {"market_slug": "market-abc", "outcome": "Yes", "shares": 10}
        ]}}
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import has_position
            assert has_position("copy-Test", "market-abc", "No") is False

    def test_misses_different_slug(self):
        responses = {"portfolio": {"ok": True, "data": [
            {"market_slug": "market-abc", "outcome": "Yes", "shares": 10}
        ]}}
        with patch("trader.subprocess.run") as mock_run:
            mock_run.side_effect = _make_run_side_effect(responses)
            from trader import has_position
            assert has_position("copy-Test", "market-xyz", "Yes") is False
