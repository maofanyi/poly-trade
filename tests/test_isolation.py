"""Verify that the isolation SAVEPOINT survives init_db() calls.

Before the fix, init_db() used executescript() which unconditionally
auto-commits and releases any active savepoint.  After the fix,
init_db() uses individual db.execute() calls for CREATE TABLE IF NOT
EXISTS, which are no-ops when tables already exist and do not commit.

This test verifies that:
1. A savepoint survives init_db() being called again
2. Data inserted inside a savepoint is rolled back correctly
"""


def test_initdb_preserves_savepoint(test_db):
    """Calling init_db() again must not release an active savepoint."""
    # Set up a savepoint (like the isolation fixture does)
    test_db.execute("SAVEPOINT _verify_initdb")
    test_db.execute("INSERT INTO wallets (address, name, category) VALUES (?, ?, ?)",
                    ("0xSAVEPOINT_TEST", "SpTest", "Test"))

    # This is the critical call — must NOT release the savepoint
    from database import init_db
    init_db()

    # Insert more data — should still be inside the savepoint
    test_db.execute("INSERT INTO wallets (address, name, category) VALUES (?, ?, ?)",
                    ("0xSAVEPOINT_TEST2", "SpTest2", "Test"))

    # Verify both rows visible
    count = test_db.execute(
        "SELECT COUNT(*) FROM wallets WHERE address LIKE '0xSAVEPOINT_TEST%'"
    ).fetchone()[0]
    assert count == 2, f"Expected 2 rows inside savepoint, got {count}"

    # Rollback — must succeed (savepoint still alive)
    test_db.execute("ROLLBACK TO _verify_initdb")

    # Verify both rows rolled back
    count = test_db.execute(
        "SELECT COUNT(*) FROM wallets WHERE address LIKE '0xSAVEPOINT_TEST%'"
    ).fetchone()[0]
    assert count == 0, f"Expected 0 rows after rollback, got {count}"
