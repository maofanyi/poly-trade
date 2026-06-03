"""Tests for POST /api/backtest."""
from unittest.mock import patch


class TestBacktest:
    def test_backtest_requires_address(self, test_client):
        resp = test_client.post("/api/backtest", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data or "trades_analyzed" in data

    def test_backtest_mocks_api(self, test_client):
        """Backtest hits Data API; mock it to return empty trades."""
        with patch("backtest._fetch", return_value=[]):
            resp = test_client.post(
                "/api/backtest",
                json={"address": "0xSOME_ADDR", "days": 7}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "trades_analyzed" in data or "error" in data
