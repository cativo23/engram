from engram.ingest.filters import should_index

MAX = 1_000_000


def test_indexes_normal_source_file():
    assert should_index("engram/agent.py", 2_000, b"def run():\n    pass\n") is True


def test_skips_oversized_file():
    assert should_index("big.py", MAX + 1, b"x = 1\n") is False


def test_skips_binary_with_null_bytes():
    assert should_index("logo.py", 50, b"\x00\x01\x02binary") is False


def test_skips_dotenv_and_secrets():
    assert should_index(".env", 10, b"SECRET=1") is False
    assert should_index("config/.env.local", 10, b"SECRET=1") is False


def test_skips_lockfiles_and_vendored_dirs():
    assert should_index("package-lock.json", 500, b"{}") is False
    assert should_index("node_modules/x/index.js", 50, b"x") is False
    assert should_index(".git/config", 50, b"x") is False


def test_skips_known_binary_extensions():
    assert should_index("img/logo.png", 50, b"\x89PNG") is False
    assert should_index("font.woff2", 50, b"x") is False


def test_does_not_skip_dotenv_lookalike():
    assert should_index(".environment", 10, b"x = 1\n") is True
