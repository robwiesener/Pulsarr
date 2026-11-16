"""
Pulsarr - Database Configuration

This module configures the SQLModel database connection.

Responsibilities
----------------
- Create the database engine
- Provide database sessions
- Initialize the database schema
- Configure SQLite for concurrent use (WAL, busy_timeout)
- Provide a transaction() context manager for multi-write paths

All database access starts here.
"""

from contextlib import contextmanager
from pathlib import Path
import os
import threading

from sqlalchemy import event

from sqlmodel import Session, SQLModel, create_engine


DB_DIR = Path(
    os.getenv("PULSARR_CONFIG_DIR", "config")
)

DB_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DATABASE_FILE = DB_DIR / "pulsarr.db"

DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Configureer SQLite voor gelijktijdig gebruik.

    - WAL: betere gelijktijdigheid van reads tijdens writes.
    - busy_timeout: wacht bij een lock in plaats van direct te falen.
    - synchronous=NORMAL: veilige balans tussen durability en snelheid.
    - foreign_keys=ON: SQLite heeft FK-afdwinging standaard uit.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


# App-brede write-serialisatie. Voorkomt "database is locked"
# bij gelijktijdige writes vanuit dezelfde process.
_write_lock = threading.RLock()


def create_db_and_tables():

    with _write_lock:
        SQLModel.metadata.create_all(engine)


def get_session():

    with Session(engine) as session:
        yield session


@contextmanager
def transaction():
    """Multi-write transactie met app-brede write-lock.

    Gebruik voor failure-paths met meerdere writes. Success-paths
    mogen gewoon session.commit() gebruiken. Houd externe
    side-effects (HTTP, notifications, logger) BUITEN deze context.
    """
    with _write_lock:
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
