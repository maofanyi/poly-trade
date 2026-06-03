"""Tests for database schema and initialization."""
import sqlite3
import pytest


class TestDatabaseSchema:
    """Verify all expected tables exist after init_db."""

    EXPECTED_TABLES = [
        "wallets", "trade_log", "pnl_snapshots", "scan_log",
        "alert_config", "alert_log", "wallet_scores",
        "discovered_wallets", "price_history", "closed_markets",
    ]

    def test_all_tables_created(self, test_db):
        rows = test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in rows]
        for table in self.EXPECTED_TABLES:
            assert table in names, f"Missing table: {table}"

    def test_wal_mode(self, test_db):
        row = test_db.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"

    def test_foreign_keys_enabled(self, test_db):
        row = test_db.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1


class TestWalletsTable:
    """Verify wallets table columns."""

    def test_wallet_columns(self, test_db):
        cols = [r[1] for r in test_db.execute("PRAGMA table_info(wallets)")]
        required = ["id", "address", "name", "category", "active", "paused", "created_at"]
        for c in required:
            assert c in cols, f"Missing wallets column: {c}"

    def test_address_unique(self, test_db):
        test_db.execute(
            "INSERT INTO wallets (address, name, category) VALUES ('0xAAA', 'W1', 'Weather')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute(
                "INSERT INTO wallets (address, name, category) VALUES ('0xAAA', 'W2', 'Sports')"
            )


class TestTradeLogColumns:
    """Verify trade_log schema."""

    def test_trade_log_columns(self, test_db):
        cols = [r[1] for r in test_db.execute("PRAGMA table_info(trade_log)")]
        required = [
            "id", "wallet_id", "txn_hash", "side", "size", "whale_price",
            "sim_usd", "fill_price", "status", "slippage", "pnl_realized",
            "slug", "outcome", "timestamp", "skip_reason",
        ]
        for c in required:
            assert c in cols, f"Missing trade_log column: {c}"


class TestMigration:
    """Verify the migrate() function adds missing columns idempotently."""

    def test_migration_idempotent(self, test_db):
        from database import migrate
        migrate()
        cols = [r[1] for r in test_db.execute("PRAGMA table_info(wallets)")]
        assert "paused" in cols
        trade_cols = [r[1] for r in test_db.execute("PRAGMA table_info(trade_log)")]
        assert "skip_reason" in trade_cols
