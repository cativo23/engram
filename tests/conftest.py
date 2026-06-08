import os

import pytest


def _test_db_url():
    return os.environ.get("ENGRAM_TEST_DATABASE_URL")


requires_db = pytest.mark.skipif(
    _test_db_url() is None,
    reason="set ENGRAM_TEST_DATABASE_URL (e.g. postgresql://engram:engram@localhost:5433/engram) to run DB tests",
)


@pytest.fixture
def db_conn():
    """A connection to the test DB with a fresh schema, truncated before each test."""
    from engram.db import connect, init_schema

    url = _test_db_url()
    with connect(url) as conn:
        init_schema(conn)
        conn.execute("TRUNCATE chunks, repos RESTART IDENTITY CASCADE")
        conn.commit()
        yield conn
