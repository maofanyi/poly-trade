"""Tests for GET /api/portfolio."""


class TestPortfolio:
    def test_portfolio_analysis_structure(self, test_client, seed_wallets):
        resp = test_client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "category_breakdown" in data
        assert "total_value" in data

    def test_portfolio_summary_shows_capital(self, test_client, seed_wallets):
        resp = test_client.get("/api/portfolio")
        data = resp.json()
        # Each wallet starts at $500; total_value accounts for all active wallets
        assert data["total_value"] >= 500
