"""Lightweight Python representations of the validated V2 SQLite schema.

These immutable dataclasses are transfer objects, not an ORM: they neither
open connections nor contain collection-domain rules.  Each ``from_row``
method maps a row returned by :mod:`database.db_manager` to its SQL-shaped
representation.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, TypeVar


T = TypeVar("T", bound="RowModel")
Numeric = int | float


@dataclass(frozen=True, slots=True)
class RowModel:
    """Base mapper for rows whose selected column names match dataclass fields."""

    @classmethod
    def from_row(cls: type[T], row: Any) -> T:
        return cls(**{field.name: row[field.name] for field in fields(cls)})


@dataclass(frozen=True, slots=True)
class Universe(RowModel):
    universe_id: int
    code: str
    name: str
    is_enabled: int
    created_at: str


@dataclass(frozen=True, slots=True)
class AppUser(RowModel):
    user_id: int
    login_name: str
    display_name: str
    password_hash: str | None
    is_active: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SecurityProfile(RowModel):
    security_profile_id: int
    profile_code: str | None
    name: str
    permissions_json: str
    is_system: int
    is_active: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class UserSecurityProfile(RowModel):
    user_id: int
    security_profile_id: int
    is_active: int
    assigned_at: str


@dataclass(frozen=True, slots=True)
class UserSettings(RowModel):
    settings_id: int
    user_id: int
    active_universe_id: int
    results_display_mode: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class NavigationState(RowModel):
    state_id: int
    user_id: int
    current_screen: str
    selected_media_id: int | None
    results_scroll_offset: int | None
    updated_at: str


@dataclass(frozen=True, slots=True)
class SourceExternal(RowModel):
    source_id: int
    code: str
    name: str
    source_type: str
    base_url: str | None
    is_enabled: int
    created_at: str


@dataclass(frozen=True, slots=True)
class UniverseSource(RowModel):
    universe_source_id: int
    universe_id: int
    source_id: int
    is_available: int
    default_priority: int | None
    configuration_text: str | None


@dataclass(frozen=True, slots=True)
class UniverseOption(RowModel):
    option_id: int
    universe_id: int
    option_kind: str
    label: str
    normalized_label: str
    sort_order: int
    is_active: int
    created_at: str


@dataclass(frozen=True, slots=True)
class Entity(RowModel):
    entity_id: int
    universe_id: int
    name: str
    normalized_name: str
    objective_reference_text: str | None
    original_name: str | None
    description: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Media(RowModel):
    media_id: int
    entity_id: int
    inventory_reference: str | None
    support_option_id: int | None
    possession_status_option_id: int | None
    acquisition_project_option_id: int | None
    sale_project_option_id: int | None
    physical_state_option_id: int | None
    current_location_id: int | None
    previous_location_path: str | None
    physical_order: int | None
    entered_on: str | None
    left_on: str | None
    maximum_purchase_price_cents: int | None
    purchase_price_cents: int | None
    estimated_value_cents: int | None
    asking_price_cents: int | None
    sale_price_cents: int | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Location(RowModel):
    location_id: int
    name: str
    normalized_name: str
    parent_location_id: int | None
    sort_order: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Classification(RowModel):
    classification_id: int
    universe_id: int
    name: str
    normalized_name: str
    application_scope: str
    is_active: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ClassificationValue(RowModel):
    classification_value_id: int
    classification_id: int
    value: str
    normalized_value: str
    sort_order: int
    is_active: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class EntityClassificationAttribution(RowModel):
    entity_id: int
    classification_value_id: int
    acquisition_mode: str
    universe_source_id: int | None
    created_at: str


@dataclass(frozen=True, slots=True)
class MediaClassificationAttribution(RowModel):
    media_id: int
    classification_value_id: int
    acquisition_mode: str
    universe_source_id: int | None
    created_at: str


@dataclass(frozen=True, slots=True)
class Document(RowModel):
    document_id: int
    storage_uri: str
    original_file_name: str
    mime_type: str
    file_size_bytes: int | None
    checksum_sha256: str | None
    is_archived: int
    created_at: str


@dataclass(frozen=True, slots=True)
class EntityDocument(RowModel):
    entity_id: int
    document_id: int
    role_option_id: int | None
    display_rank: int
    acquisition_mode: str
    universe_source_id: int | None
    created_at: str


@dataclass(frozen=True, slots=True)
class MediaDocument(RowModel):
    media_id: int
    document_id: int
    role_option_id: int | None
    display_rank: int
    acquisition_mode: str
    universe_source_id: int | None
    created_at: str


@dataclass(frozen=True, slots=True)
class EntityInformation(RowModel):
    entity_information_id: int
    entity_id: int
    field_code: str
    value_type: str
    value_text: str | None
    value_integer: int | None
    value_decimal: Numeric | None
    value_date: str | None
    value_json: str | None
    updated_at: str


@dataclass(frozen=True, slots=True)
class MediaInformation(RowModel):
    media_information_id: int
    media_id: int
    field_code: str
    value_type: str
    value_text: str | None
    value_integer: int | None
    value_decimal: Numeric | None
    value_date: str | None
    value_json: str | None
    updated_at: str


@dataclass(frozen=True, slots=True)
class EntityInformationOrigin(RowModel):
    origin_id: int
    entity_id: int
    entity_information_id: int
    field_code: str
    value_snapshot: str | None
    universe_source_id: int | None
    external_id_snapshot: str | None
    external_url_snapshot: str | None
    acquisition_mode: str
    recorded_at: str


@dataclass(frozen=True, slots=True)
class MediaInformationOrigin(RowModel):
    origin_id: int
    media_id: int
    media_information_id: int
    field_code: str
    value_snapshot: str | None
    universe_source_id: int | None
    external_id_snapshot: str | None
    external_url_snapshot: str | None
    acquisition_mode: str
    recorded_at: str
