"""Global test fixtures."""
import os
import sys
import time

# Ensure root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DB_PATH before ANY project imports.
# config.DB_PATH is a module-level constant evaluated at import time,
# so the env var must be set before database/config are imported.
import tempfile as _tempfile
_TEST_DB_PATH = os.path.join(
    _tempfile.gettempdir(),
    f"test_trade_{os.getpid()}.db"
)
os.environ["DB_PATH"] = _TEST_DB_PATH
os.environ["SCAN_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from database import get_db, init_db, _local


@pytest.fixture(scope="session")
def test_db():
    """Session-scoped temp-file SQLite with all tables created once.

    Uses a temp file instead of :memory: to avoid shared-cache mode, which
    leaks data between connections and breaks transaction-based isolation.
    """
    # Remove any stale file from a previous crashed session
    if os.path.exists(_TEST_DB_PATH):
        try:
            os.unlink(_TEST_DB_PATH)
        except OSError:
            pass
    _local.db = None
    init_db()
    db = get_db()
    yield db
    # Reset thread-local so no dangling reference keeps WAL files open on Windows
    _local.db = None
    db.close()
    time.sleep(0.05)
    try:
        os.unlink(_TEST_DB_PATH)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def isolation(test_db):
    """Wrap each test in a transaction, rollback after.

    FastAPI endpoints use get_db() which returns the same thread-local
    connection as test_db, so all API changes are also rolled back.
    """
    test_db.execute("SAVEPOINT _test_isolation")
    yield
    # init_db() calls executescript() which issues COMMIT, releasing savepoints.
    # Gracefully handle the case where the savepoint no longer exists.
    try:
        test_db.execute("ROLLBACK TO _test_isolation")
    except Exception:
        pass  # savepoint already released (e.g., by init_db -> executescript)


@pytest.fixture
def test_client(test_db):
    """FastAPI TestClient with scanner disabled."""
    from main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def seed_wallets(test_db):
    """Insert 2 test wallets, return list of dicts."""
    test_db.execute(
        "INSERT INTO wallets (address, name, category) VALUES (?, ?, ?)",
        ("0xAAA", "TestWallet1", "Weather")
    )
    test_db.execute(
        "INSERT INTO wallets (address, name, category) VALUES (?, ?, ?)",
        ("0xBBB", "TestWallet2", "Politics")
    )
    test_db.commit()
    wallets = test_db.execute("SELECT * FROM wallets WHERE active = 1").fetchall()
    return [dict(w) for w in wallets]
