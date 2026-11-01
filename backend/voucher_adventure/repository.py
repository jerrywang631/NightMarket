"""Database adapters for Voucher Adventure session state."""

from contextlib import contextmanager
from datetime import datetime, timezone
import os
import sqlite3


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class VoucherTransaction:
    def __init__(self, cursor, dialect):
        self.cursor = cursor
        self.dialect = dialect

    def _sql(self, query):
        return query.replace("?", "%s") if self.dialect == "postgres" else query

    @staticmethod
    def _row(row):
        if row is None:
            return None
        return dict(row)

    def execute(self, query, params=()):
        self.cursor.execute(self._sql(query), tuple(params))
        return self.cursor

    def one(self, query, params=()):
        return self._row(self.execute(query, params).fetchone())

    def all(self, query, params=()):
        return [self._row(row) for row in self.execute(query, params).fetchall()]

    def many(self, query, rows):
        self.cursor.executemany(self._sql(query), rows)


class VoucherSessionRepository:
    dialect = None

    def __init__(self, migrations):
        self.migrations = migrations

    def connect(self):
        raise NotImplementedError

    def initialize(self):
        raise NotImplementedError

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            cursor = connection.cursor()
            if self.dialect == "sqlite":
                cursor.execute("BEGIN IMMEDIATE")
            transaction = VoucherTransaction(cursor, self.dialect)
            yield transaction
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def lock_key(self, transaction, key):
        """Serialize idempotency and active-session checks in PostgreSQL."""
        if self.dialect == "postgres":
            transaction.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (key,))

    def fetch_one(self, query, params=()):
        with self.transaction() as transaction:
            return transaction.one(query, params)

    def fetch_all(self, query, params=()):
        with self.transaction() as transaction:
            return transaction.all(query, params)


class SQLiteVoucherSessionRepository(VoucherSessionRepository):
    dialect = "sqlite"

    def __init__(self, database_path, migrations):
        super().__init__(migrations)
        self.database_path = os.path.abspath(database_path)
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        connection = self.connect()
        try:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS voucher_schema_migrations (
                       version TEXT PRIMARY KEY,
                       applied_at TEXT NOT NULL
                   )"""
            )
            for version, migration_path in self.migrations:
                applied = connection.execute(
                    "SELECT 1 FROM voucher_schema_migrations WHERE version = ?",
                    (version,),
                ).fetchone()
                if applied:
                    continue
                with open(migration_path, encoding="utf-8") as migration_file:
                    connection.executescript(migration_file.read())
                connection.execute(
                    "INSERT INTO voucher_schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, _utc_now()),
                )
            connection.commit()
        finally:
            connection.close()


class PostgresVoucherSessionRepository(VoucherSessionRepository):
    dialect = "postgres"

    def __init__(self, database_url, migrations):
        self.database_url = database_url
        super().__init__(migrations)
        self.initialize()

    def connect(self):
        import psycopg2
        import psycopg2.extras

        return psycopg2.connect(
            self.database_url,
            sslmode="require",
            cursor_factory=psycopg2.extras.RealDictCursor,
        )

    def initialize(self):
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS voucher_schema_migrations (
                           version TEXT PRIMARY KEY,
                           applied_at TEXT NOT NULL
                       )"""
                )
                for version, migration_path in self.migrations:
                    cursor.execute(
                        "SELECT 1 FROM voucher_schema_migrations WHERE version = %s",
                        (version,),
                    )
                    if cursor.fetchone():
                        continue
                    with open(migration_path, encoding="utf-8") as migration_file:
                        cursor.execute(migration_file.read())
                    cursor.execute(
                        """INSERT INTO voucher_schema_migrations (version, applied_at)
                           VALUES (%s, %s)""",
                        (version, _utc_now()),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def create_voucher_repository(database_url=None, sqlite_path=None):
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    migrations_dir = os.path.join(backend_dir, "migrations")
    database_url = database_url or os.environ.get("DATABASE_URL")
    if database_url:
        migrations = [
            (
                "001_voucher_adventure_sessions",
                os.path.join(
                    migrations_dir, "001_voucher_adventure_sessions.postgres.sql"
                ),
            ),
            (
                "002_voucher_content_v1",
                os.path.join(migrations_dir, "002_voucher_content_v1.postgres.sql"),
            ),
        ]
        return PostgresVoucherSessionRepository(
            database_url,
            migrations,
        )

    sqlite_path = (
        sqlite_path
        or os.environ.get("VOUCHER_SQLITE_PATH")
        or os.path.join(backend_dir, "database", "voucher_sessions.db")
    )
    migrations = [
        (
            "001_voucher_adventure_sessions",
            os.path.join(migrations_dir, "001_voucher_adventure_sessions.sqlite.sql"),
        ),
        (
            "002_voucher_content_v1",
            os.path.join(migrations_dir, "002_voucher_content_v1.sqlite.sql"),
        ),
    ]
    return SQLiteVoucherSessionRepository(sqlite_path, migrations)
