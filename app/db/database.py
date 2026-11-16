"""
Pulsarr - Database Configuration

This module configures the SQLModel database connection.

Responsibilities
----------------
- Create the database engine
- Provide database sessions
- Initialize the database schema

All database access starts here.
"""

from pathlib import Path
import os

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
)


def create_db_and_tables():

    SQLModel.metadata.create_all(engine)


def get_session():

    with Session(engine) as session:
        yield session