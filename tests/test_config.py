"""Tests for config.py constants and env var behavior."""
import os
import sys
import pytest


class TestPmTraderConfig:
    """Verify pm-trader --data-dir is correctly constructed."""

    def test_pm_trader_includes_data_dir(self, monkeypatch):
        monkeypatch.setenv("PM_DATA_DIR", "/tmp/pm-test")
        if "config" in sys.modules:
            del sys.modules["config"]
        from config import PM_TRADER, PM_DATA_DIR
        assert "pm-trader --data-dir" in PM_TRADER
        assert PM_DATA_DIR in PM_TRADER

    def test_default_data_dir_under_data(self, monkeypatch):
        monkeypatch.delenv("PM_DATA_DIR", raising=False)
        if "config" in sys.modules:
            del sys.modules["config"]
        from config import PM_DATA_DIR
        assert "data" in PM_DATA_DIR
        assert "pm-trader" in PM_DATA_DIR

    def test_custom_data_dir_via_env(self, monkeypatch):
        monkeypatch.setenv("PM_DATA_DIR", "/custom/path")
        if "config" in sys.modules:
            del sys.modules["config"]
        from config import PM_DATA_DIR
        assert PM_DATA_DIR == "/custom/path"


class TestOtherConfig:
    """Basic config sanity checks."""

    def test_init_capital_positive(self):
        from config import INITIAL_CAPITAL
        assert INITIAL_CAPITAL == 500.0

    def test_scan_interval_default(self, monkeypatch):
        monkeypatch.delenv("SCAN_INTERVAL", raising=False)
        if "config" in sys.modules:
            del sys.modules["config"]
        from config import SCAN_INTERVAL
        assert SCAN_INTERVAL == 5

    def test_scan_interval_env(self, monkeypatch):
        monkeypatch.setenv("SCAN_INTERVAL", "60")
        if "config" in sys.modules:
            del sys.modules["config"]
        from config import SCAN_INTERVAL
        assert SCAN_INTERVAL == 60

    def test_data_api_url(self):
        from config import DATA_API
        assert DATA_API == "https://data-api.polymarket.com"
