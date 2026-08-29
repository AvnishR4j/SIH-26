import os
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("ENVIRONMENT", "test")

TEST_DATABASE_PATH = BACKEND_ROOT / f".test-kalasetu-{os.getpid()}.db"
TEST_MEDIA_PATH = BACKEND_ROOT / f".test-media-{os.getpid()}"
TEST_DATABASE_PATH.unlink(missing_ok=True)
shutil.rmtree(TEST_MEDIA_PATH, ignore_errors=True)
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{TEST_DATABASE_PATH}")
os.environ.setdefault("DATABASE_AUTO_CREATE", "true")
os.environ.setdefault("MEDIA_LOCAL_DIR", str(TEST_MEDIA_PATH))
os.environ.setdefault("MEDIA_URL_BASE", "http://testserver/media")


def pytest_sessionfinish() -> None:
    from app.db.session import get_database

    get_database().dispose()
    TEST_DATABASE_PATH.unlink(missing_ok=True)
    shutil.rmtree(TEST_MEDIA_PATH, ignore_errors=True)
