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
    """Wrap each test in a SAVEPOINT, rollback after.

    Uses SAVEPOINT instead of BEGIN/ROLLBACK because some code paths
    (e.g., init_db via FastAPI lifespan) may issue commits that release
    the savepoint.  The cleanup is best-effort: if the savepoint is
    still alive, the test's changes are reverted; if it was released,
    we log at debug level and move on.

    CRITICAL: init_db() no longer calls executescript() which would
    unconditionally release the savepoint.  It now uses individual
    db.execute() calls for each CREATE TABLE IF NOT EXISTS, which are
    no-ops when tables already exist and do not auto-commit.
    """
    import logging
    _logger = logging.getLogger("tests.isolation")
    test_db.execute("SAVEPOINT _test_isolation")
    yield
    try:
        test_db.execute("ROLLBACK TO _test_isolation")
    except Exception:
        _logger.debug("_test_isolation savepoint already released")


@pytest.fixture
def test_client(test_db):
    """FastAPI TestClient with scanner disabled.

    Note: FastAPI runs synchronous endpoint handlers in a thread pool.
    Each worker thread gets its own connection via get_db(), so changes
    made through test_client are committed on separate connections and
    are NOT rolled back by the isolation fixture's SAVEPOINT (which
    only covers the test_db connection on the main thread).
    """
    from main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def seed_wallets(test_db):
    """Insert 2 test wallets, return list of dicts.

    No explicit commit — the isolation fixture wraps each test in a
    SAVEPOINT, so uncommitted inserts are visible to subsequent
    SELECTs on the same connection and are cleaned up on teardown.
    """
    test_db.execute(
        "INSERT OR IGNORE INTO wallets (address, name, category) VALUES (?, ?, ?)",
        ("0xAAA", "TestWallet1", "Weather")
    )
    test_db.execute(
        "INSERT OR IGNORE INTO wallets (address, name, category) VALUES (?, ?, ?)",
        ("0xBBB", "TestWallet2", "Politics")
    )
    wallets = test_db.execute("SELECT * FROM wallets WHERE active = 1").fetchall()
    return [dict(w) for w in wallets]
