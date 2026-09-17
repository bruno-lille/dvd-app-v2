"""Minimal durable USER_SETTINGS service for V2."""

from __future__ import annotations

from database.db_manager import connect, transaction
from database.models import UserSettings


class SettingsServiceError(RuntimeError):
    """Base error for USER_SETTINGS operations."""


class SettingsNotFoundError(SettingsServiceError):
    """Raised when an active USER_SETTINGS record cannot be found."""


class SettingsValidationError(SettingsServiceError):
    """Raised when a requested durable preference is outside its universe scope."""


def get_settings(user_id: int) -> UserSettings | None:
    """Return the durable settings belonging to one USER, if present."""
    connection = connect()
    try:
        return _get_settings(connection, user_id)
    finally:
        connection.close()


def set_active_universe(user_id: int, universe_id: int) -> UserSettings:
    """Change only the USER's active collection context."""
    with transaction() as connection:
        _require_settings(connection, user_id)
        if connection.execute("SELECT 1 FROM universe WHERE universe_id = ?", (universe_id,)).fetchone() is None:
            raise SettingsValidationError(f"UNIVERSE {universe_id} does not exist.")
        connection.execute("UPDATE user_settings SET active_universe_id = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (universe_id, user_id))
        return _require_settings(connection, user_id)


def set_display_preferences(user_id: int, *, results_display_mode: str) -> UserSettings:
    """Update the only display preference currently represented by the schema."""
    if not isinstance(results_display_mode, str) or not results_display_mode.strip():
        raise SettingsValidationError("results_display_mode is required.")
    with transaction() as connection:
        _require_settings(connection, user_id)
        connection.execute("UPDATE user_settings SET results_display_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (results_display_mode.strip(), user_id))
        return _require_settings(connection, user_id)


def hide_classification(user_id: int, classification_id: int) -> None:
    """Hide a generic CLASSIFICATION in the USER's active universe."""
    with transaction() as connection:
        settings = _require_settings(connection, user_id)
        _require_classification_in_active_universe(connection, settings, classification_id)
        connection.execute("INSERT OR IGNORE INTO user_settings_hidden_classification (settings_id, classification_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (settings.settings_id, classification_id))


def unhide_classification(user_id: int, classification_id: int) -> None:
    """Remove only the visibility preference; no collection data is deleted."""
    with transaction() as connection:
        settings = _require_settings(connection, user_id)
        _require_classification_in_active_universe(connection, settings, classification_id)
        connection.execute("DELETE FROM user_settings_hidden_classification WHERE settings_id = ? AND classification_id = ?", (settings.settings_id, classification_id))


def hide_classification_value(user_id: int, classification_value_id: int) -> None:
    """Hide a generic CLASSIFICATION_VALUE in the USER's active universe."""
    with transaction() as connection:
        settings = _require_settings(connection, user_id)
        _require_value_in_active_universe(connection, settings, classification_value_id)
        connection.execute("INSERT OR IGNORE INTO user_settings_hidden_classification_value (settings_id, classification_value_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (settings.settings_id, classification_value_id))


def unhide_classification_value(user_id: int, classification_value_id: int) -> None:
    """Remove only a VALUE visibility preference."""
    with transaction() as connection:
        settings = _require_settings(connection, user_id)
        _require_value_in_active_universe(connection, settings, classification_value_id)
        connection.execute("DELETE FROM user_settings_hidden_classification_value WHERE settings_id = ? AND classification_value_id = ?", (settings.settings_id, classification_value_id))


def _get_settings(connection, user_id: int) -> UserSettings | None:
    row = connection.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    return UserSettings.from_row(row) if row is not None else None


def _require_settings(connection, user_id: int) -> UserSettings:
    settings = _get_settings(connection, user_id)
    if settings is None:
        raise SettingsNotFoundError(f"USER_SETTINGS for USER {user_id} does not exist.")
    return settings


def _require_classification_in_active_universe(connection, settings: UserSettings, classification_id: int) -> None:
    row = connection.execute("SELECT 1 FROM classification WHERE classification_id = ? AND universe_id = ?", (classification_id, settings.active_universe_id)).fetchone()
    if row is None:
        raise SettingsValidationError("CLASSIFICATION does not belong to the active universe.")


def _require_value_in_active_universe(connection, settings: UserSettings, classification_value_id: int) -> None:
    row = connection.execute(
        "SELECT 1 FROM classification_value value JOIN classification classification ON classification.classification_id = value.classification_id WHERE value.classification_value_id = ? AND classification.universe_id = ?",
        (classification_value_id, settings.active_universe_id),
    ).fetchone()
    if row is None:
        raise SettingsValidationError("CLASSIFICATION_VALUE does not belong to the active universe.")
