from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_TABLES = {
    "users",
    "otp_requests",
    "otp_attempts",
    "otp_idempotency",
    "catalog_drafts",
    "draft_create_idempotency",
    "media_objects",
    "image_upload_idempotency",
    "operations",
    "operation_idempotency",
    "voice_media",
    "voice_upload_idempotency",
    "pricing_benchmarks",
    "pricing_suggestion_idempotency",
}


def test_migrations_upgrade_match_models_and_downgrade(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert APPLICATION_TABLES.issubset(set(inspect(engine).get_table_names()))
    command.check(config)

    command.downgrade(config, "base")
    assert not APPLICATION_TABLES.intersection(inspect(engine).get_table_names())
    engine.dispose()
