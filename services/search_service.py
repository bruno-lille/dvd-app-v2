"""SQL-backed, single-universe search for V2 MEDIA results.

This module models the small filter vocabulary used by the future mobile UI;
it is not a general boolean-expression language and contains no UI code.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from database.db_manager import connect


MatchMode = Literal["ALL", "ANY"]
_OPTION_COLUMNS = {
    "SUPPORT": "support_option_id",
    "POSSESSION_STATUS": "possession_status_option_id",
    "ACQUISITION_PROJECT": "acquisition_project_option_id",
    "SALE_PROJECT": "sale_project_option_id",
    "PHYSICAL_STATE": "physical_state_option_id",
}


class SearchValidationError(ValueError):
    """Raised when a search request does not match the V2 model scope."""


@dataclass(frozen=True, slots=True)
class ClassificationFilter:
    """One generic classification block and its selected VALUE identifiers."""

    classification_id: int
    value_ids: tuple[int, ...]
    match_mode: MatchMode = "ANY"


@dataclass(frozen=True, slots=True)
class StructuralOptionFilter:
    """One MEDIA structural option block, scoped by its technical option kind."""

    option_kind: str
    option_ids: tuple[int, ...]
    match_mode: MatchMode = "ANY"


SearchFilter = ClassificationFilter | StructuralOptionFilter


@dataclass(frozen=True, slots=True)
class SearchGroup:
    """Blocks combined with """"Tous les critères"""" (AND)."""

    filters: tuple[SearchFilter, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """A single-universe search with optional flat OR alternatives.

    The primary group and each alternative group are ORed together.  Within a
    group, blocks are ANDed; within a block, ``ALL`` means all values and
    ``ANY`` means at least one value.
    """

    universe_id: int
    user_settings_id: int
    text: str | None = None
    group: SearchGroup = field(default_factory=SearchGroup)
    alternatives: tuple[SearchGroup, ...] = ()
    include_hidden: bool = False
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True, slots=True)
class SearchResult:
    """The minimal MEDIA-oriented information needed by the future result list."""

    media_id: int
    entity_id: int
    universe_id: int
    entity_name: str
    inventory_reference: str | None
    support_label: str | None
    possession_status_label: str | None
    current_location_id: int | None
    current_location_name: str | None


@dataclass(frozen=True, slots=True)
class SearchPage:
    results: tuple[SearchResult, ...]
    total_count: int
    page: int
    page_size: int


def search(request: SearchRequest) -> SearchPage:
    """Return paginated MEDIA results strictly limited to ``request.universe_id``."""

    _validate_request_shape(request)
    connection = connect()
    try:
        _require_universe(connection, request.universe_id)
        _require_settings(connection, request.user_settings_id)
        where_clauses, parameters = _build_where_clause(connection, request)
        where_sql = " AND ".join(where_clauses)
        count_sql = (
            "SELECT COUNT(*) FROM media m JOIN entity e ON e.entity_id = m.entity_id "
            f"WHERE {where_sql}"
        )
        total_count = connection.execute(count_sql, parameters).fetchone()[0]
        result_sql = f"""
            SELECT
                m.media_id, e.entity_id, e.universe_id, e.name AS entity_name,
                m.inventory_reference, support.label AS support_label,
                possession.label AS possession_status_label,
                m.current_location_id, location.name AS current_location_name
            FROM media m
            JOIN entity e ON e.entity_id = m.entity_id
            LEFT JOIN universe_option support ON support.option_id = m.support_option_id
            LEFT JOIN universe_option possession ON possession.option_id = m.possession_status_option_id
            LEFT JOIN location ON location.location_id = m.current_location_id
            WHERE {where_sql}
            ORDER BY e.normalized_name, e.entity_id, m.media_id
            LIMIT ? OFFSET ?
        """
        offset = (request.page - 1) * request.page_size
        rows = connection.execute(result_sql, (*parameters, request.page_size, offset)).fetchall()
        return SearchPage(
            results=tuple(SearchResult(**dict(row)) for row in rows),
            total_count=total_count,
            page=request.page,
            page_size=request.page_size,
        )
    finally:
        connection.close()


def _build_where_clause(connection, request: SearchRequest) -> tuple[list[str], list[object]]:
    clauses = ["e.universe_id = ?"]
    parameters: list[object] = [request.universe_id]
    if request.text and request.text.strip():
        normalized_text = _normalize_text(request.text)
        raw_like = f"%{request.text.strip()}%"
        clauses.append(
            "(" 
            "e.normalized_name LIKE ? OR e.original_name LIKE ? COLLATE NOCASE OR "
            "e.objective_reference_text LIKE ? COLLATE NOCASE OR e.description LIKE ? COLLATE NOCASE OR "
            "m.inventory_reference LIKE ? COLLATE NOCASE"
            ")"
        )
        parameters.extend((f"%{normalized_text}%", raw_like, raw_like, raw_like, raw_like))
    if not request.include_hidden:
        visibility_sql, visibility_parameters = _visibility_predicate(request.user_settings_id)
        clauses.append(visibility_sql)
        parameters.extend(visibility_parameters)

    groups = (request.group, *request.alternatives)
    group_sql: list[str] = []
    group_parameters: list[object] = []
    for group in groups:
        predicate, predicate_parameters = _group_predicate(connection, request.universe_id, group)
        group_sql.append(f"({predicate})")
        group_parameters.extend(predicate_parameters)
    if len(group_sql) > 1:
        clauses.append("(" + " OR ".join(group_sql) + ")")
    elif group_sql and group_sql[0] != "(1 = 1)":
        clauses.append(group_sql[0])
    parameters.extend(group_parameters)
    return clauses, parameters


def _group_predicate(connection, universe_id: int, group: SearchGroup) -> tuple[str, list[object]]:
    if not group.filters:
        return "1 = 1", []
    predicates: list[str] = []
    parameters: list[object] = []
    for search_filter in group.filters:
        if isinstance(search_filter, ClassificationFilter):
            predicate, values = _classification_predicate(connection, universe_id, search_filter)
        elif isinstance(search_filter, StructuralOptionFilter):
            predicate, values = _option_predicate(connection, universe_id, search_filter)
        else:
            raise SearchValidationError("Unsupported search filter.")
        predicates.append(predicate)
        parameters.extend(values)
    return " AND ".join(predicates), parameters


def _classification_predicate(
    connection, universe_id: int, search_filter: ClassificationFilter
) -> tuple[str, list[object]]:
    _validate_match_values(search_filter.value_ids, search_filter.match_mode, "classification")
    row = connection.execute(
        "SELECT application_scope FROM classification WHERE classification_id = ? AND universe_id = ?",
        (search_filter.classification_id, universe_id),
    ).fetchone()
    if row is None:
        raise SearchValidationError("Classification does not belong to the requested universe.")
    placeholders = ", ".join("?" for _ in search_filter.value_ids)
    valid_value_count = connection.execute(
        f"SELECT COUNT(*) FROM classification_value WHERE classification_id = ? AND classification_value_id IN ({placeholders})",
        (search_filter.classification_id, *search_filter.value_ids),
    ).fetchone()[0]
    if valid_value_count != len(set(search_filter.value_ids)):
        raise SearchValidationError("A selected VALUE does not belong to this CLASSIFICATION.")

    scope = row["application_scope"]
    value_source_sql = _classification_value_source(scope, placeholders)
    value_parameters = list(search_filter.value_ids) * (2 if scope == "BOTH" else 1)
    if search_filter.match_mode == "ANY":
        return f"EXISTS ({value_source_sql})", value_parameters
    return (
        f"(SELECT COUNT(DISTINCT classification_value_id) FROM ({value_source_sql})) = ?",
        [*value_parameters, len(search_filter.value_ids)],
    )


def _classification_value_source(scope: str, placeholders: str) -> str:
    entity_source = f"""
        SELECT a.classification_value_id
        FROM entity_classification_attribution a
        WHERE a.entity_id = e.entity_id AND a.classification_value_id IN ({placeholders})
    """
    media_source = f"""
        SELECT a.classification_value_id
        FROM media_classification_attribution a
        WHERE a.media_id = m.media_id AND a.classification_value_id IN ({placeholders})
    """
    if scope == "ENTITY":
        return entity_source
    if scope == "MEDIA":
        return media_source
    if scope == "BOTH":
        return f"{entity_source} UNION {media_source}"
    raise SearchValidationError("Unknown CLASSIFICATION application scope.")


def _option_predicate(
    connection, universe_id: int, search_filter: StructuralOptionFilter
) -> tuple[str, list[object]]:
    _validate_match_values(search_filter.option_ids, search_filter.match_mode, "option")
    column = _OPTION_COLUMNS.get(search_filter.option_kind)
    if column is None:
        raise SearchValidationError("Unsupported structural option kind.")
    placeholders = ", ".join("?" for _ in search_filter.option_ids)
    valid_count = connection.execute(
        f"SELECT COUNT(*) FROM universe_option WHERE universe_id = ? AND option_kind = ? AND option_id IN ({placeholders})",
        (universe_id, search_filter.option_kind, *search_filter.option_ids),
    ).fetchone()[0]
    if valid_count != len(set(search_filter.option_ids)):
        raise SearchValidationError("A structural option does not belong to the requested universe and kind.")
    if search_filter.match_mode == "ANY":
        return f"m.{column} IN ({placeholders})", list(search_filter.option_ids)
    return (
        f"m.{column} IN ({placeholders}) AND EXISTS ("
        f"SELECT 1 FROM media sibling_media "
        f"WHERE sibling_media.entity_id = e.entity_id "
        f"AND sibling_media.{column} IN ({placeholders}) "
        f"GROUP BY sibling_media.entity_id "
        f"HAVING COUNT(DISTINCT sibling_media.{column}) = ?"
        f")",
        [*search_filter.option_ids, *search_filter.option_ids, len(search_filter.option_ids)],
    )


def _visibility_predicate(settings_id: int) -> tuple[str, list[object]]:
    hidden_for_entity = """
        SELECT 1
        FROM entity_classification_attribution a
        JOIN classification_value v ON v.classification_value_id = a.classification_value_id
        WHERE a.entity_id = e.entity_id AND (
            EXISTS (SELECT 1 FROM user_settings_hidden_classification h
                    WHERE h.settings_id = ? AND h.classification_id = v.classification_id)
            OR EXISTS (SELECT 1 FROM user_settings_hidden_classification_value h
                       WHERE h.settings_id = ? AND h.classification_value_id = v.classification_value_id)
        )
    """
    hidden_for_media = """
        SELECT 1
        FROM media_classification_attribution a
        JOIN classification_value v ON v.classification_value_id = a.classification_value_id
        WHERE a.media_id = m.media_id AND (
            EXISTS (SELECT 1 FROM user_settings_hidden_classification h
                    WHERE h.settings_id = ? AND h.classification_id = v.classification_id)
            OR EXISTS (SELECT 1 FROM user_settings_hidden_classification_value h
                       WHERE h.settings_id = ? AND h.classification_value_id = v.classification_value_id)
        )
    """
    return f"NOT EXISTS ({hidden_for_entity}) AND NOT EXISTS ({hidden_for_media})", [settings_id] * 4


def _validate_request_shape(request: SearchRequest) -> None:
    if request.universe_id <= 0:
        raise SearchValidationError("universe_id is required.")
    if request.page <= 0 or request.page_size <= 0:
        raise SearchValidationError("page and page_size must be positive.")
    if request.alternatives and not request.group.filters:
        raise SearchValidationError("An alternative requires a non-empty primary group.")
    if any(not group.filters for group in request.alternatives):
        raise SearchValidationError("An alternative group must contain at least one filter.")


def _validate_match_values(values: tuple[int, ...], match_mode: str, label: str) -> None:
    if match_mode not in ("ALL", "ANY"):
        raise SearchValidationError("match_mode must be ALL or ANY.")
    if not values or len(set(values)) != len(values):
        raise SearchValidationError(f"A {label} filter requires distinct selected values.")


def _require_universe(connection, universe_id: int) -> None:
    if connection.execute("SELECT 1 FROM universe WHERE universe_id = ?", (universe_id,)).fetchone() is None:
        raise SearchValidationError("Requested universe does not exist.")


def _require_settings(connection, settings_id: int) -> None:
    if connection.execute("SELECT 1 FROM user_settings WHERE settings_id = ?", (settings_id,)).fetchone() is None:
        raise SearchValidationError("USER_SETTINGS does not exist.")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", normalized)
