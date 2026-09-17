"""Current ENTITY_INFORMATION values and per-information provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from database.db_manager import connect, transaction
from database.models import EntityInformation, EntityInformationOrigin


class EntityInformationError(RuntimeError): pass
class EntityInformationNotFoundError(EntityInformationError): pass
class EntityInformationValidationError(EntityInformationError): pass
class EntityInformationAlreadyExistsError(EntityInformationError): pass


@dataclass(frozen=True, slots=True)
class EntityInformationWithOrigins:
    information: EntityInformation
    origins: tuple[EntityInformationOrigin, ...]


_VALUE_COLUMNS = {"TEXT": "value_text", "INTEGER": "value_integer", "DECIMAL": "value_decimal", "DATE": "value_date", "JSON": "value_json"}
_ACQUISITION_MODES = {"MANUAL", "AUTOMATIC", "MIGRATED_LEGACY"}


def get_information(entity_id: int, field_code: str) -> EntityInformationWithOrigins | None:
    """Read one current value and all retained provenance records for it."""
    clean_code = _field_code(field_code)
    connection = connect()
    try:
        information = _get_information(connection, entity_id, clean_code)
        return _with_origins(connection, information) if information else None
    finally: connection.close()


def list_entity_information(entity_id: int) -> tuple[EntityInformationWithOrigins, ...]:
    """Read all current values, each with its provenance history."""
    connection = connect()
    try:
        _require_entity(connection, entity_id)
        rows = connection.execute("SELECT * FROM entity_information WHERE entity_id = ? ORDER BY field_code", (entity_id,)).fetchall()
        return tuple(_with_origins(connection, EntityInformation.from_row(row)) for row in rows)
    finally: connection.close()


def set_information(*, entity_id: int, field_code: str, value_type: str, value: Any, acquisition_mode: str, universe_source_id: int | None = None, external_id_snapshot: str | None = None, external_url_snapshot: str | None = None, expected_universe_id: int | None = None) -> EntityInformationWithOrigins:
    """Create a new current value. Existing values require explicit replacement."""
    clean_code, clean_type = _field_code(field_code), _value_type(value_type)
    with transaction() as connection:
        entity_universe = _require_entity(connection, entity_id)
        _validate_expected_universe(entity_universe, expected_universe_id)
        if _get_information(connection, entity_id, clean_code):
            raise EntityInformationAlreadyExistsError("Information already exists; use replace_information explicitly.")
        _validate_provenance(connection, entity_universe, acquisition_mode, universe_source_id)
        values = _value_columns(clean_type, value)
        cursor = connection.execute(
            "INSERT INTO entity_information (entity_id, field_code, value_type, value_text, value_integer, value_decimal, value_date, value_json, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (entity_id, clean_code, clean_type, values["value_text"], values["value_integer"], values["value_decimal"], values["value_date"], values["value_json"]),
        )
        information = _require_information(connection, cursor.lastrowid)
        _insert_origin(connection, information, acquisition_mode, universe_source_id, external_id_snapshot, external_url_snapshot)
        return _with_origins(connection, information)


def replace_information(*, entity_id: int, field_code: str, value_type: str, value: Any, acquisition_mode: str, universe_source_id: int | None = None, external_id_snapshot: str | None = None, external_url_snapshot: str | None = None, expected_universe_id: int | None = None) -> EntityInformationWithOrigins:
    """Explicitly replace the current value and append its new provenance record."""
    clean_code, clean_type = _field_code(field_code), _value_type(value_type)
    with transaction() as connection:
        entity_universe = _require_entity(connection, entity_id)
        _validate_expected_universe(entity_universe, expected_universe_id)
        information = _get_information(connection, entity_id, clean_code)
        if information is None:
            raise EntityInformationNotFoundError("Information does not exist; use set_information first.")
        _validate_provenance(connection, entity_universe, acquisition_mode, universe_source_id)
        values = _value_columns(clean_type, value)
        connection.execute(
            "UPDATE entity_information SET value_type = ?, value_text = ?, value_integer = ?, value_decimal = ?, value_date = ?, value_json = ?, updated_at = CURRENT_TIMESTAMP WHERE entity_information_id = ?",
            (clean_type, values["value_text"], values["value_integer"], values["value_decimal"], values["value_date"], values["value_json"], information.entity_information_id),
        )
        current = _require_information(connection, information.entity_information_id)
        _insert_origin(connection, current, acquisition_mode, universe_source_id, external_id_snapshot, external_url_snapshot)
        return _with_origins(connection, current)


def _with_origins(connection, information: EntityInformation) -> EntityInformationWithOrigins:
    rows = connection.execute("SELECT * FROM entity_information_origin WHERE entity_information_id = ? ORDER BY recorded_at, origin_id", (information.entity_information_id,)).fetchall()
    return EntityInformationWithOrigins(information, tuple(EntityInformationOrigin.from_row(row) for row in rows))


def _get_information(connection, entity_id: int, field_code: str) -> EntityInformation | None:
    row = connection.execute("SELECT * FROM entity_information WHERE entity_id = ? AND field_code = ?", (entity_id, field_code)).fetchone()
    return EntityInformation.from_row(row) if row else None


def _require_information(connection, information_id: int) -> EntityInformation:
    row = connection.execute("SELECT * FROM entity_information WHERE entity_information_id = ?", (information_id,)).fetchone()
    if not row: raise EntityInformationNotFoundError("ENTITY_INFORMATION does not exist.")
    return EntityInformation.from_row(row)


def _require_entity(connection, entity_id: int) -> int:
    row = connection.execute("SELECT universe_id FROM entity WHERE entity_id = ?", (entity_id,)).fetchone()
    if not row: raise EntityInformationNotFoundError(f"ENTITY {entity_id} does not exist.")
    return row["universe_id"]


def _insert_origin(connection, information: EntityInformation, acquisition_mode: str, universe_source_id: int | None, external_id_snapshot: str | None, external_url_snapshot: str | None) -> None:
    connection.execute(
        "INSERT INTO entity_information_origin (entity_id, entity_information_id, field_code, value_snapshot, universe_source_id, external_id_snapshot, external_url_snapshot, acquisition_mode, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (information.entity_id, information.entity_information_id, information.field_code, _snapshot(information), universe_source_id, external_id_snapshot, external_url_snapshot, acquisition_mode),
    )


def _validate_provenance(connection, entity_universe: int, acquisition_mode: str, universe_source_id: int | None) -> None:
    if acquisition_mode not in _ACQUISITION_MODES: raise EntityInformationValidationError("Unsupported acquisition_mode.")
    if acquisition_mode == "AUTOMATIC" and universe_source_id is None: raise EntityInformationValidationError("AUTOMATIC provenance requires a universe source.")
    if universe_source_id is not None:
        row = connection.execute("SELECT 1 FROM universe_source WHERE universe_source_id = ? AND universe_id = ? AND is_available = 1", (universe_source_id, entity_universe)).fetchone()
        if not row: raise EntityInformationValidationError("UNIVERS_SOURCE is not available for the ENTITY universe.")


def _validate_expected_universe(entity_universe: int, expected_universe: int | None) -> None:
    if expected_universe is not None and expected_universe != entity_universe: raise EntityInformationValidationError("ENTITY does not belong to the expected universe.")


def _field_code(value: str) -> str:
    if not isinstance(value, str) or not (clean := value.strip()): raise EntityInformationValidationError("field_code is required.")
    return clean


def _value_type(value: str) -> str:
    if value not in _VALUE_COLUMNS: raise EntityInformationValidationError("Unsupported value_type.")
    return value


def _value_columns(value_type: str, value: Any) -> dict[str, Any]:
    columns = {column: None for column in _VALUE_COLUMNS.values()}
    column = _VALUE_COLUMNS[value_type]
    if value_type == "JSON":
        columns[column] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    elif value_type == "INTEGER":
        if not isinstance(value, int): raise EntityInformationValidationError("INTEGER information requires an integer value.")
        columns[column] = value
    elif value_type == "DECIMAL":
        if not isinstance(value, (int, float)): raise EntityInformationValidationError("DECIMAL information requires a numeric value.")
        columns[column] = value
    elif not isinstance(value, str): raise EntityInformationValidationError(f"{value_type} information requires a text value.")
    else: columns[column] = value
    return columns


def _snapshot(information: EntityInformation) -> str | None:
    for column in _VALUE_COLUMNS.values():
        value = getattr(information, column)
        if value is not None: return str(value)
    return None
