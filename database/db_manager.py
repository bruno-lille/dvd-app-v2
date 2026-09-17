"""SQLite connection and transaction support for the V2 collection database.

This module deliberately contains no collection-domain behaviour.  Future V2
services use its connection helpers instead of resolving ``collection.db``
themselves.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "collection.db"


class DatabaseError(RuntimeError):
    """Raised when a SQLite operation managed by this module fails."""


def get_database_path() -> Path:
    """Return the absolute V2 database path, independent of the launch folder."""

    return DATABASE_PATH


def connect() -> sqlite3.Connection:
    """Open a configured connection to ``collection.db``.

    Foreign-key checking is explicitly enabled because SQLite applies that
    setting per connection.  Callers using this low-level function own the
    transaction and must commit/rollback and close the returned connection.
    """

    try:
        connection = sqlite3.connect(DATABASE_PATH, isolation_level="DEFERRED")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except sqlite3.Error as exc:
        raise DatabaseError(f"Unable to open V2 collection database: {exc}") from exc


@contextmanager
def transaction() -> Generator[sqlite3.Connection, None, None]:
    """Yield a connection in a transaction, committing or rolling back safely."""

    connection = connect()
    try:
        connection.execute("BEGIN")
        yield connection
    except sqlite3.Error as exc:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
        raise DatabaseError(f"V2 database transaction failed: {exc}") from exc
    except Exception:
        try:
            connection.rollback()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Unable to roll back V2 database transaction: {exc}") from exc
        raise
    else:
        try:
            connection.commit()
        except sqlite3.Error as exc:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
            raise DatabaseError(f"Unable to commit V2 database transaction: {exc}") from exc
    finally:
        try:
            connection.close()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Unable to close V2 database connection: {exc}") from exc
