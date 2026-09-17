"""Reference management for SOURCE_EXTERNE and UNIVERS_SOURCE."""

from __future__ import annotations

from database.db_manager import connect, transaction
from database.models import SourceExternal, UniverseSource


_UNSET = object()


class SourceServiceError(RuntimeError):
    """Base error for external-source reference operations."""


class SourceNotFoundError(SourceServiceError):
    """Raised when a requested SOURCE_EXTERNE or UNIVERS_SOURCE is absent."""


class SourceValidationError(SourceServiceError):
    """Raised when a requested source operation is outside the SQL model scope."""


def get_source(source_id: int) -> SourceExternal | None:
    """Return one source, including a disabled source, or ``None``."""
    connection = connect()
    try:
        return _get_source(connection, source_id)
    finally:
        connection.close()


def list_sources(*, include_inactive: bool = True) -> tuple[SourceExternal, ...]:
    """List the source reference catalogue without contacting any source."""
    connection = connect()
    try:
        sql = "SELECT * FROM source_external"
        if not include_inactive:
            sql += " WHERE is_enabled = 1"
        rows = connection.execute(sql + " ORDER BY name, source_id").fetchall()
        return tuple(SourceExternal.from_row(row) for row in rows)
    finally:
        connection.close()


def create_source(*, code: str, name: str, source_type: str, base_url: str | None = None) -> SourceExternal:
    """Create a source with a stable, user-supplied internal code."""
    clean_code = _require_text(code, "code")
    clean_name = _require_text(name, "name")
    with transaction() as connection:
        if connection.execute("SELECT 1 FROM source_external WHERE code = ?", (clean_code,)).fetchone() is not None:
            raise SourceValidationError("A SOURCE_EXTERNE already uses this code.")
        cursor = connection.execute(
            "INSERT INTO source_external (code, name, source_type, base_url, is_enabled, created_at) VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
            (clean_code, clean_name, source_type, _empty_to_none(base_url)),
        )
        return _require_source(connection, cursor.lastrowid)


def update_source(source_id: int, *, name: str | None = None, source_type: str | None = None, base_url: str | None | object = _UNSET) -> SourceExternal:
    """Update mutable source metadata; the stable source code is not editable."""
    with transaction() as connection:
        source = _require_source(connection, source_id)
        new_name = source.name if name is None else _require_text(name, "name")
        new_type = source.source_type if source_type is None else source_type
        new_url = source.base_url if base_url is _UNSET else _empty_to_none(base_url)
        connection.execute("UPDATE source_external SET name = ?, source_type = ?, base_url = ? WHERE source_id = ?", (new_name, new_type, new_url, source_id))
        return _require_source(connection, source_id)


def activate_source(source_id: int) -> SourceExternal:
    return _set_source_activation(source_id, True)


def deactivate_source(source_id: int) -> SourceExternal:
    """Disable a source without removing its links or provenance."""
    return _set_source_activation(source_id, False)


def attach_source_to_universe(universe_id: int, source_id: int, *, is_available: bool = True, default_priority: int | None = None, configuration_text: str | None = None) -> UniverseSource:
    """Make a reusable source available in one universe."""
    with transaction() as connection:
        _require_universe(connection, universe_id)
        _require_source(connection, source_id)
        if connection.execute("SELECT 1 FROM universe_source WHERE universe_id = ? AND source_id = ?", (universe_id, source_id)).fetchone() is not None:
            raise SourceValidationError("This SOURCE_EXTERNE is already attached to this UNIVERSE.")
        cursor = connection.execute(
            "INSERT INTO universe_source (universe_id, source_id, is_available, default_priority, configuration_text) VALUES (?, ?, ?, ?, ?)",
            (universe_id, source_id, int(is_available), default_priority, _empty_to_none(configuration_text)),
        )
        return _require_universe_source(connection, cursor.lastrowid)


def detach_source_from_universe(universe_source_id: int) -> None:
    """Detach an unused association; used associations must be deactivated instead."""
    with transaction() as connection:
        _require_universe_source(connection, universe_source_id)
        if _universe_source_is_referenced(connection, universe_source_id):
            raise SourceValidationError("This UNIVERS_SOURCE is already referenced; deactivate it instead of detaching it.")
        connection.execute("DELETE FROM universe_source WHERE universe_source_id = ?", (universe_source_id,))


def list_universe_sources(universe_id: int, *, include_unavailable: bool = True) -> tuple[UniverseSource, ...]:
    """List source availability records for one universe."""
    connection = connect()
    try:
        _require_universe(connection, universe_id)
        sql = "SELECT * FROM universe_source WHERE universe_id = ?"
        if not include_unavailable:
            sql += " AND is_available = 1"
        rows = connection.execute(sql + " ORDER BY default_priority, universe_source_id", (universe_id,)).fetchall()
        return tuple(UniverseSource.from_row(row) for row in rows)
    finally:
        connection.close()


def _set_source_activation(source_id: int, is_enabled: bool) -> SourceExternal:
    with transaction() as connection:
        _require_source(connection, source_id)
        connection.execute("UPDATE source_external SET is_enabled = ? WHERE source_id = ?", (int(is_enabled), source_id))
        return _require_source(connection, source_id)


def _get_source(connection, source_id: int) -> SourceExternal | None:
    row = connection.execute("SELECT * FROM source_external WHERE source_id = ?", (source_id,)).fetchone()
    return SourceExternal.from_row(row) if row is not None else None


def _require_source(connection, source_id: int) -> SourceExternal:
    source = _get_source(connection, source_id)
    if source is None:
        raise SourceNotFoundError(f"SOURCE_EXTERNE {source_id} does not exist.")
    return source


def _require_universe(connection, universe_id: int) -> None:
    if connection.execute("SELECT 1 FROM universe WHERE universe_id = ?", (universe_id,)).fetchone() is None:
        raise SourceValidationError(f"UNIVERSE {universe_id} does not exist.")


def _require_universe_source(connection, universe_source_id: int) -> UniverseSource:
    row = connection.execute("SELECT * FROM universe_source WHERE universe_source_id = ?", (universe_source_id,)).fetchone()
    if row is None:
        raise SourceNotFoundError(f"UNIVERS_SOURCE {universe_source_id} does not exist.")
    return UniverseSource.from_row(row)


def _universe_source_is_referenced(connection, universe_source_id: int) -> bool:
    tables = (
        "user_settings_source_preference", "entity_document", "media_document",
        "entity_external_reference", "media_external_reference",
        "entity_information_origin", "media_information_origin",
    )
    return any(connection.execute(f"SELECT 1 FROM {table} WHERE universe_source_id = ? LIMIT 1", (universe_source_id,)).fetchone() is not None for table in tables)


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not (clean := value.strip()):
        raise SourceValidationError(f"{label} is required.")
    return clean


def _empty_to_none(value: str | None | object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SourceValidationError("Optional text must be a string or None.")
    return value.strip() or None
