"""Tests for scores.py — wallet scoring and discovery."""
from unittest.mock import patch


class TestScoreWallet:
    def test_score_no_trades_returns_empty(self):
        from scores import score_wallet
        with patch("scores._fetch", return_value=[]):
            result = score_wallet("0xEMPTY")
        assert result is not None
        assert result["trades"] == 0
        assert result["score"] == 0

    def test_score_with_trades(self):
        from scores import score_wallet
        canned = []
        for i in range(20):
            side = "BUY" if i % 2 == 0 else "SELL"
            canned.append({
                "transactionHash": f"0xS{i}",
                "side": side,
                "size": 50,
                "price": 0.5,
                "timestamp": 1700000000 + i * 60,
                "conditionId": f"cond-{i % 5}",
            })

        with patch("scores._fetch", return_value=canned):
            result = score_wallet("0xGOOD")

        assert result is not None
        assert result["trades"] == 20
        assert result["markets"] == 5
        assert result["score"] > 0

    def test_score_api_error_returns_none(self):
        from scores import score_wallet
        with patch("scores._fetch", side_effect=Exception("Network error")):
            result = score_wallet("0xBAD")
        assert result is None


class TestRefreshAllScores:
    def test_refresh_updates_db(self, test_db):
        """refresh_all_scores commits internally, so use a unique wallet and clean up."""
        from scores import refresh_all_scores

        # Use a unique wallet to avoid polluting other tests
        test_db.execute(
            "INSERT INTO wallets (address, name, category) VALUES ('0xSCORE_TEST', 'ScoreTest', 'Sports')"
        )
        test_db.commit()
        w = test_db.execute(
            "SELECT * FROM wallets WHERE address = '0xSCORE_TEST'"
        ).fetchone()

        canned = [{
            "transactionHash": "0xRS",
            "side": "BUY",
            "size": 100,
            "price": 0.6,
            "timestamp": 1700000000,
            "conditionId": "cond-1",
        }]

        with patch("scores._fetch", return_value=canned):
            refresh_all_scores()

        row = test_db.execute(
            "SELECT * FROM wallet_scores WHERE wallet_id = ?", (w["id"],)
        ).fetchone()
        assert row is not None

        # Clean up to avoid leaking into other tests
        test_db.execute("DELETE FROM wallet_scores WHERE wallet_id = ?", (w["id"],))
        test_db.execute("DELETE FROM wallets WHERE id = ?", (w["id"],))
        test_db.commit()
