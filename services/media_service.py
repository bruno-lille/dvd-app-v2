"""Minimal V2 service for ENTITY and MEDIA.

The service applies only the rules needed to manipulate their structural data.
SQLite constraints and triggers remain the final integrity protection.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Final

from database.db_manager import connect, transaction
from database.models import Entity, Media, UniverseOption


class MediaServiceError(RuntimeError):
    """Base error raised when a requested ENTITY or MEDIA operation is invalid."""


class NotFoundError(MediaServiceError):
    """Raised when a requested V2 object does not exist."""


class ValidationError(MediaServiceError):
    """Raised when supplied structural data violates a service-level rule."""


@dataclass(frozen=True, slots=True)
class EntityWithMedia:
    """An ENTITY and its explicitly attached MEDIA, without inherited data."""

    entity: Entity
    media: tuple[Media, ...]


_UNSET: Final = object()
_MEDIA_OPTION_KINDS: Final = {
    "support_option_id": "SUPPORT",
    "possession_status_option_id": "POSSESSION_STATUS",
    "acquisition_project_option_id": "ACQUISITION_PROJECT",
    "sale_project_option_id": "SALE_PROJECT",
    "physical_state_option_id": "PHYSICAL_STATE",
}


def get_entity(entity_id: int) -> Entity | None:
    """Return one ENTITY, or ``None`` when it does not exist."""

    connection = connect()
    try:
        return _get_entity(connection, entity_id)
    finally:
        connection.close()


def get_entity_with_media(entity_id: int) -> EntityWithMedia | None:
    """Return an ENTITY and its MEDIA; classifications are intentionally absent."""

    connection = connect()
    try:
        entity = _get_entity(connection, entity_id)
        if entity is None:
            return None
        rows = connection.execute(
            "SELECT * FROM media WHERE entity_id = ? ORDER BY media_id", (entity_id,)
        ).fetchall()
        return EntityWithMedia(entity=entity, media=tuple(Media.from_row(row) for row in rows))
    finally:
        connection.close()


def get_media(media_id: int) -> Media | None:
    """Return one MEDIA, or ``None`` when it does not exist."""

    connection = connect()
    try:
        return _get_media(connection, media_id)
    finally:
        connection.close()


def create_entity(
    *,
    universe_id: int,
    name: str,
    objective_reference_text: str | None = None,
    original_name: str | None = None,
    description: str | None = None,
    connection: sqlite3.Connection | None = None,
) -> Entity:
    """Create an ENTITY in an explicitly chosen universe.

    Homonymous ENTITY records are not merged.  A distinct objective reference
    is required when the normalized name already exists in that universe.
    """

    clean_name, normalized_name = _prepare_name(name)
    objective_reference_text = _empty_to_none(objective_reference_text)
    if connection is not None:
        return _create_entity(
            connection,
            universe_id=universe_id,
            name=clean_name,
            normalized_name=normalized_name,
            objective_reference_text=objective_reference_text,
            original_name=original_name,
            description=description,
        )
    with transaction() as transaction_connection:
        return _create_entity(
            transaction_connection,
            universe_id=universe_id,
            name=clean_name,
            normalized_name=normalized_name,
            objective_reference_text=objective_reference_text,
            original_name=original_name,
            description=description,
        )


def update_entity(
    entity_id: int,
    *,
    name: str | object = _UNSET,
    objective_reference_text: str | None | object = _UNSET,
    original_name: str | None | object = _UNSET,
    description: str | None | object = _UNSET,
) -> Entity:
    """Update mutable structural ENTITY fields without changing its identity."""

    with transaction() as connection:
        entity = _require_entity(connection, entity_id)
        new_name, new_normalized_name = (
            _prepare_name(name) if name is not _UNSET else (entity.name, entity.normalized_name)
        )
        new_reference = (
            _empty_to_none(objective_reference_text)
            if objective_reference_text is not _UNSET
            else entity.objective_reference_text
        )
        _require_objective_reference_for_homonym(
            connection,
            entity.universe_id,
            new_normalized_name,
            new_reference,
            excluded_entity_id=entity_id,
        )
        connection.execute(
            """
            UPDATE entity
            SET name = ?, normalized_name = ?, objective_reference_text = ?,
                original_name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE entity_id = ?
            """,
            (
                new_name,
                new_normalized_name,
                new_reference,
                _empty_to_none(original_name) if original_name is not _UNSET else entity.original_name,
                _empty_to_none(description) if description is not _UNSET else entity.description,
                entity_id,
            ),
        )
        return _require_entity(connection, entity_id)


def create_media(
    *,
    entity_id: int,
    inventory_reference: str | None = None,
    support_option_id: int | None = None,
    possession_status_option_id: int | None = None,
    acquisition_project_option_id: int | None = None,
    sale_project_option_id: int | None = None,
    physical_state_option_id: int | None = None,
    current_location_id: int | None = None,
    physical_order: int | None = None,
    entered_on: str | None = None,
    left_on: str | None = None,
    maximum_purchase_price_cents: int | None = None,
    purchase_price_cents: int | None = None,
    estimated_value_cents: int | None = None,
    asking_price_cents: int | None = None,
    sale_price_cents: int | None = None,
) -> Media:
    """Create one identifiable MEDIA attached to an existing ENTITY."""

    values = {
        "support_option_id": support_option_id,
        "possession_status_option_id": possession_status_option_id,
        "acquisition_project_option_id": acquisition_project_option_id,
        "sale_project_option_id": sale_project_option_id,
        "physical_state_option_id": physical_state_option_id,
    }
    with transaction() as connection:
        entity = _require_entity(connection, entity_id)
        _validate_media_options(connection, entity.universe_id, values)
        _validate_location(connection, current_location_id)
        cursor = connection.execute(
            """
            INSERT INTO media (
                entity_id, inventory_reference, support_option_id, possession_status_option_id,
                acquisition_project_option_id, sale_project_option_id, physical_state_option_id,
                current_location_id, physical_order, entered_on, left_on,
                maximum_purchase_price_cents, purchase_price_cents, estimated_value_cents,
                asking_price_cents, sale_price_cents, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                entity_id,
                _empty_to_none(inventory_reference),
                support_option_id,
                possession_status_option_id,
                acquisition_project_option_id,
                sale_project_option_id,
                physical_state_option_id,
                current_location_id,
                physical_order,
                entered_on,
                left_on,
                maximum_purchase_price_cents,
                purchase_price_cents,
                estimated_value_cents,
                asking_price_cents,
                sale_price_cents,
            ),
        )
        return _require_media(connection, cursor.lastrowid)


def update_media(
    media_id: int,
    *,
    inventory_reference: str | None | object = _UNSET,
    support_option_id: int | None | object = _UNSET,
    possession_status_option_id: int | None | object = _UNSET,
    acquisition_project_option_id: int | None | object = _UNSET,
    sale_project_option_id: int | None | object = _UNSET,
    physical_state_option_id: int | None | object = _UNSET,
    physical_order: int | None | object = _UNSET,
    entered_on: str | None | object = _UNSET,
    left_on: str | None | object = _UNSET,
    maximum_purchase_price_cents: int | None | object = _UNSET,
    purchase_price_cents: int | None | object = _UNSET,
    estimated_value_cents: int | None | object = _UNSET,
    asking_price_cents: int | None | object = _UNSET,
    sale_price_cents: int | None | object = _UNSET,
) -> Media:
    """Update mutable MEDIA fields; identifiers, ENTITY and location are excluded."""

    with transaction() as connection:
        media = _require_media(connection, media_id)
        entity = _require_entity(connection, media.entity_id)
        proposed = {
            field: getattr(media, field) if value is _UNSET else value
            for field, value in {
                "support_option_id": support_option_id,
                "possession_status_option_id": possession_status_option_id,
                "acquisition_project_option_id": acquisition_project_option_id,
                "sale_project_option_id": sale_project_option_id,
                "physical_state_option_id": physical_state_option_id,
            }.items()
        }
        _validate_media_options(connection, entity.universe_id, proposed)
        updates = {
            "inventory_reference": _empty_to_none(inventory_reference)
            if inventory_reference is not _UNSET
            else media.inventory_reference,
            **proposed,
            "physical_order": media.physical_order if physical_order is _UNSET else physical_order,
            "entered_on": media.entered_on if entered_on is _UNSET else entered_on,
            "left_on": media.left_on if left_on is _UNSET else left_on,
            "maximum_purchase_price_cents": media.maximum_purchase_price_cents
            if maximum_purchase_price_cents is _UNSET
            else maximum_purchase_price_cents,
            "purchase_price_cents": media.purchase_price_cents if purchase_price_cents is _UNSET else purchase_price_cents,
            "estimated_value_cents": media.estimated_value_cents if estimated_value_cents is _UNSET else estimated_value_cents,
            "asking_price_cents": media.asking_price_cents if asking_price_cents is _UNSET else asking_price_cents,
            "sale_price_cents": media.sale_price_cents if sale_price_cents is _UNSET else sale_price_cents,
        }
        _update_media_values(connection, media_id, updates)
        return _require_media(connection, media_id)


def update_media_situation(
    media_id: int,
    *,
    possession_status_option_id: int | None | object = _UNSET,
    acquisition_project_option_id: int | None | object = _UNSET,
    sale_project_option_id: int | None | object = _UNSET,
    entered_on: str | None | object = _UNSET,
    left_on: str | None | object = _UNSET,
) -> Media:
    """Update situation and explicitly supplied collection dates without deletion.

    Option labels are deliberately not interpreted: callers decide which date,
    if any, corresponds to the user's chosen generic option.
    """

    return update_media(
        media_id,
        possession_status_option_id=possession_status_option_id,
        acquisition_project_option_id=acquisition_project_option_id,
        sale_project_option_id=sale_project_option_id,
        entered_on=entered_on,
        left_on=left_on,
    )


def set_media_location(media_id: int, location_id: int | None) -> Media:
    """Set the current LOCATION and freeze the last path when it changes."""

    with transaction() as connection:
        media = _require_media(connection, media_id)
        _validate_location(connection, location_id)
        if media.current_location_id == location_id:
            return media
        previous_path = media.previous_location_path
        if media.current_location_id is not None:
            previous_path = _build_location_path(connection, media.current_location_id)
        connection.execute(
            """
            UPDATE media
            SET current_location_id = ?, previous_location_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE media_id = ?
            """,
            (location_id, previous_path, media_id),
        )
        return _require_media(connection, media_id)


def list_structural_options(
    universe_id: int, *, option_kind: str | None = None, include_inactive: bool = False
) -> tuple[UniverseOption, ...]:
    """List user-configurable structural options available in one universe."""

    connection = connect()
    try:
        _require_universe(connection, universe_id)
        clauses = ["universe_id = ?"]
        parameters: list[object] = [universe_id]
        if option_kind is not None:
            clauses.append("option_kind = ?")
            parameters.append(option_kind)
        if not include_inactive:
            clauses.append("is_active = 1")
        rows = connection.execute(
            f"SELECT * FROM universe_option WHERE {' AND '.join(clauses)} "
            "ORDER BY option_kind, sort_order, label",
            parameters,
        ).fetchall()
        return tuple(UniverseOption.from_row(row) for row in rows)
    finally:
        connection.close()


def _get_entity(connection, entity_id: int) -> Entity | None:
    row = connection.execute("SELECT * FROM entity WHERE entity_id = ?", (entity_id,)).fetchone()
    return Entity.from_row(row) if row is not None else None


def _create_entity(
    connection: sqlite3.Connection,
    *,
    universe_id: int,
    name: str,
    normalized_name: str,
    objective_reference_text: str | None,
    original_name: str | None,
    description: str | None,
) -> Entity:
    """Create an ENTITY on a caller-owned or locally-owned transaction."""

    _require_universe(connection, universe_id)
    _require_objective_reference_for_homonym(
        connection, universe_id, normalized_name, objective_reference_text
    )
    cursor = connection.execute(
        """
        INSERT INTO entity (
            universe_id, name, normalized_name, objective_reference_text,
            original_name, description, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            universe_id,
            name,
            normalized_name,
            objective_reference_text,
            _empty_to_none(original_name),
            _empty_to_none(description),
        ),
    )
    return _require_entity(connection, cursor.lastrowid)


def _get_media(connection, media_id: int) -> Media | None:
    row = connection.execute("SELECT * FROM media WHERE media_id = ?", (media_id,)).fetchone()
    return Media.from_row(row) if row is not None else None


def _require_entity(connection, entity_id: int) -> Entity:
    entity = _get_entity(connection, entity_id)
    if entity is None:
        raise NotFoundError(f"ENTITY {entity_id} does not exist.")
    return entity


def _require_media(connection, media_id: int) -> Media:
    media = _get_media(connection, media_id)
    if media is None:
        raise NotFoundError(f"MEDIA {media_id} does not exist.")
    return media


def _require_universe(connection, universe_id: int) -> None:
    if connection.execute("SELECT 1 FROM universe WHERE universe_id = ?", (universe_id,)).fetchone() is None:
        raise ValidationError(f"UNIVERSE {universe_id} does not exist.")


def _validate_media_options(connection, universe_id: int, options: dict[str, int | None]) -> None:
    for field_name, option_id in options.items():
        if option_id is None:
            continue
        expected_kind = _MEDIA_OPTION_KINDS[field_name]
        row = connection.execute(
            """
            SELECT 1 FROM universe_option
            WHERE option_id = ? AND universe_id = ? AND option_kind = ?
            """,
            (option_id, universe_id, expected_kind),
        ).fetchone()
        if row is None:
            raise ValidationError(
                f"{field_name} must reference a {expected_kind} option from the ENTITY universe."
            )


def _validate_location(connection, location_id: int | None) -> None:
    if location_id is None:
        return
    if connection.execute("SELECT 1 FROM location WHERE location_id = ?", (location_id,)).fetchone() is None:
        raise ValidationError(f"LOCATION {location_id} does not exist.")


def _build_location_path(connection, location_id: int) -> str:
    names: list[str] = []
    seen: set[int] = set()
    current_id: int | None = location_id
    while current_id is not None:
        if current_id in seen:
            raise ValidationError("LOCATION hierarchy contains a cycle.")
        seen.add(current_id)
        row = connection.execute(
            "SELECT location_id, name, parent_location_id FROM location WHERE location_id = ?",
            (current_id,),
        ).fetchone()
        if row is None:
            raise ValidationError(f"LOCATION {current_id} does not exist.")
        names.append(row["name"])
        current_id = row["parent_location_id"]
    return " / ".join(reversed(names))


def _update_media_values(connection, media_id: int, values: dict[str, object]) -> None:
    assignments = ", ".join(f"{column} = ?" for column in values)
    connection.execute(
        f"UPDATE media SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE media_id = ?",
        (*values.values(), media_id),
    )


def _require_objective_reference_for_homonym(
    connection,
    universe_id: int,
    normalized_name: str,
    objective_reference_text: str | None,
    *,
    excluded_entity_id: int | None = None,
) -> None:
    query = "SELECT 1 FROM entity WHERE universe_id = ? AND normalized_name = ?"
    parameters: list[object] = [universe_id, normalized_name]
    if excluded_entity_id is not None:
        query += " AND entity_id <> ?"
        parameters.append(excluded_entity_id)
    has_homonym = connection.execute(query, parameters).fetchone() is not None
    if has_homonym and objective_reference_text is None:
        raise ValidationError(
            "An objective reference is required when an ENTITY has the same name in this universe."
        )


def _prepare_name(name: str) -> tuple[str, str]:
    if not isinstance(name, str) or not (clean_name := name.strip()):
        raise ValidationError("ENTITY name is required.")
    normalized_name = _normalize_name(clean_name)
    if not normalized_name:
        raise ValidationError("ENTITY name must contain at least one letter or digit.")
    return clean_name, normalized_name


def _normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", normalized)


def _empty_to_none(value: str | None | object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Text fields must be strings or None.")
    return value.strip() or None
