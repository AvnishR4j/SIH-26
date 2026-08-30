from functools import lru_cache
from threading import RLock

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base


class Database:
    def __init__(self, settings: Settings) -> None:
        database_url = normalize_database_url(settings.database_url)
        connect_args: dict[str, object] = {}
        engine_options: dict[str, object] = {
            "echo": settings.database_echo,
            "pool_pre_ping": True,
        }
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            if database_url.endswith(":memory:"):
                engine_options["poolclass"] = StaticPool

        self.engine = create_engine(
            database_url,
            connect_args=connect_args,
            **engine_options,
        )
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )
        self.write_lock = RLock()
        if settings.database_auto_create:
            self.create_schema()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def session(self) -> Session:
        return self.session_factory()

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        self._seed_reference_data()

    def _seed_reference_data(self) -> None:
        from app.db.models import PricingBenchmark
        from app.db.reference_data import PRICING_BENCHMARKS

        with self.session() as session, session.begin():
            existing = set(session.scalars(select(PricingBenchmark.category)))
            session.add_all(
                PricingBenchmark(**row)
                for row in PRICING_BENCHMARKS
                if row["category"] not in existing
            )

    def drop_schema(self) -> None:
        Base.metadata.drop_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()

    def is_available(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


@lru_cache
def get_database() -> Database:
    return Database(get_settings())
