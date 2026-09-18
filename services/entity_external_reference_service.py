"""ENTITY external identifiers scoped through UNIVERS_SOURCE."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from database.db_manager import connect, transaction


class EntityExternalReferenceError(RuntimeError): pass
class EntityExternalReferenceNotFoundError(EntityExternalReferenceError): pass
class EntityExternalReferenceValidationError(EntityExternalReferenceError): pass
class EntityExternalReferenceAlreadyExistsError(EntityExternalReferenceError): pass


@dataclass(frozen=True, slots=True)
class EntityExternalReference:
    entity_external_reference_id: int
    entity_id: int
    universe_source_id: int
    external_id: str | None
    external_url: str | None
    last_retrieved_at: str | None
    created_at: str


def get_external_reference(entity_id: int, universe_source_id: int, *, connection: sqlite3.Connection | None = None) -> EntityExternalReference | None:
    """Read a reference, optionally through a caller-owned connection."""
    if connection is not None:
        return _get_reference(connection, entity_id, universe_source_id)
    connection = connect()
    try: return _get_reference(connection, entity_id, universe_source_id)
    finally: connection.close()


def list_external_references(entity_id: int, *, connection: sqlite3.Connection | None = None) -> tuple[EntityExternalReference, ...]:
    """List references, optionally through a caller-owned connection."""
    if connection is not None:
        return _list_external_references(connection, entity_id)
    connection = connect()
    try:
        return _list_external_references(connection, entity_id)
    finally: connection.close()


def set_external_reference(*, entity_id: int, universe_source_id: int, external_id: str, external_url: str | None = None, last_retrieved_at: str | None = None, connection: sqlite3.Connection | None = None) -> EntityExternalReference:
    """Create one explicit current reference; never overwrite an existing source link."""
    clean_id = _external_id(external_id)
    if connection is not None:
        return _set_external_reference(
            connection, entity_id, universe_source_id, clean_id, external_url, last_retrieved_at
        )
    with transaction() as transaction_connection:
        return _set_external_reference(
            transaction_connection, entity_id, universe_source_id, clean_id, external_url, last_retrieved_at
        )


def replace_external_reference(*, entity_id: int, universe_source_id: int, external_id: str, external_url: str | None = None, last_retrieved_at: str | None = None, connection: sqlite3.Connection | None = None) -> EntityExternalReference:
    """Explicitly replace an existing external identifier for the same source."""
    clean_id = _external_id(external_id)
    if connection is not None:
        return _replace_external_reference(
            connection, entity_id, universe_source_id, clean_id, external_url, last_retrieved_at
        )
    with transaction() as transaction_connection:
        return _replace_external_reference(
            transaction_connection, entity_id, universe_source_id, clean_id, external_url, last_retrieved_at
        )


def _get_reference(connection, entity_id: int, universe_source_id: int) -> EntityExternalReference | None:
    row = connection.execute("SELECT * FROM entity_external_reference WHERE entity_id = ? AND universe_source_id = ? ORDER BY entity_external_reference_id LIMIT 1", (entity_id, universe_source_id)).fetchone()
    return _from_row(row) if row else None


def _list_external_references(connection: sqlite3.Connection, entity_id: int) -> tuple[EntityExternalReference, ...]:
    _require_entity_universe(connection, entity_id)
    rows = connection.execute("SELECT * FROM entity_external_reference WHERE entity_id = ? ORDER BY universe_source_id, entity_external_reference_id", (entity_id,)).fetchall()
    return tuple(_from_row(row) for row in rows)


def _set_external_reference(connection: sqlite3.Connection, entity_id: int, universe_source_id: int, external_id: str, external_url: str | None, last_retrieved_at: str | None) -> EntityExternalReference:
    entity_universe = _require_entity_universe(connection, entity_id)
    _require_universe_source(connection, universe_source_id, entity_universe)
    if _get_reference(connection, entity_id, universe_source_id):
        raise EntityExternalReferenceAlreadyExistsError("External reference already exists; use replace_external_reference explicitly.")
    _ensure_external_id_available(connection, universe_source_id, external_id)
    cursor = connection.execute("INSERT INTO entity_external_reference (entity_id, universe_source_id, external_id, external_url, last_retrieved_at, created_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (entity_id, universe_source_id, external_id, _empty_to_none(external_url), last_retrieved_at))
    return _require_reference_by_id(connection, cursor.lastrowid)


def _replace_external_reference(connection: sqlite3.Connection, entity_id: int, universe_source_id: int, external_id: str, external_url: str | None, last_retrieved_at: str | None) -> EntityExternalReference:
    entity_universe = _require_entity_universe(connection, entity_id)
    _require_universe_source(connection, universe_source_id, entity_universe)
    reference = _get_reference(connection, entity_id, universe_source_id)
    if reference is None: raise EntityExternalReferenceNotFoundError("External reference does not exist; use set_external_reference first.")
    _ensure_external_id_available(connection, universe_source_id, external_id, excluded_reference_id=reference.entity_external_reference_id)
    connection.execute("UPDATE entity_external_reference SET external_id = ?, external_url = ?, last_retrieved_at = ? WHERE entity_external_reference_id = ?", (external_id, _empty_to_none(external_url), last_retrieved_at, reference.entity_external_reference_id))
    return _require_reference_by_id(connection, reference.entity_external_reference_id)


def _from_row(row) -> EntityExternalReference:
    return EntityExternalReference(**dict(row))


def _require_reference_by_id(connection, reference_id: int) -> EntityExternalReference:
    row = connection.execute("SELECT * FROM entity_external_reference WHERE entity_external_reference_id = ?", (reference_id,)).fetchone()
    if not row: raise EntityExternalReferenceNotFoundError("ENTITY_EXTERNAL_REFERENCE does not exist.")
    return _from_row(row)


def _require_entity_universe(connection, entity_id: int) -> int:
    row = connection.execute("SELECT universe_id FROM entity WHERE entity_id = ?", (entity_id,)).fetchone()
    if not row: raise EntityExternalReferenceNotFoundError(f"ENTITY {entity_id} does not exist.")
    return row["universe_id"]


def _require_universe_source(connection, universe_source_id: int, universe_id: int) -> None:
    row = connection.execute(
        "SELECT universe_id, is_available FROM universe_source WHERE universe_source_id = ?",
        (universe_source_id,),
    ).fetchone()
    if not row:
        raise EntityExternalReferenceNotFoundError(
            f"UNIVERSE_SOURCE {universe_source_id} does not exist."
        )
    if row["universe_id"] != universe_id or row["is_available"] != 1:
        raise EntityExternalReferenceValidationError(
            "UNIVERSE_SOURCE is not available for the ENTITY universe."
        )


def _ensure_external_id_available(connection, universe_source_id: int, external_id: str, *, excluded_reference_id: int | None = None) -> None:
    sql = "SELECT 1 FROM entity_external_reference WHERE universe_source_id = ? AND external_id = ?"
    parameters: list[object] = [universe_source_id, external_id]
    if excluded_reference_id is not None:
        sql += " AND entity_external_reference_id <> ?"; parameters.append(excluded_reference_id)
    if connection.execute(sql, parameters).fetchone(): raise EntityExternalReferenceAlreadyExistsError("This external identifier is already used by this source.")


def _external_id(value: str) -> str:
    if not isinstance(value, str) or not (clean := value.strip()): raise EntityExternalReferenceValidationError("external_id is required.")
    return clean


def _empty_to_none(value: str | None) -> str | None:
    if value is None: return None
    if not isinstance(value, str): raise EntityExternalReferenceValidationError("Optional text must be a string or None.")
    return value.strip() or None
