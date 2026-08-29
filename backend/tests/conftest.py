import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("ENVIRONMENT", "test")

TEST_DATABASE_PATH = BACKEND_ROOT / f".test-kalasetu-{os.getpid()}.db"
TEST_DATABASE_PATH.unlink(missing_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{TEST_DATABASE_PATH}")
os.environ.setdefault("DATABASE_AUTO_CREATE", "true")


def pytest_sessionfinish() -> None:
    from app.db.session import get_database

    get_database().dispose()
    TEST_DATABASE_PATH.unlink(missing_ok=True)
