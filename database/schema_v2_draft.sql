-- DVD APP V2 — SCHEMA DRAFT
-- Draft only. Do not execute against collection.db without explicit approval.
-- SQLite connections must enable foreign-key enforcement.

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

CREATE TABLE universe (
    universe_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL
);

-- Technical representation of the validated USER object.
-- The initial seed creates exactly one local user; authentication is not active.
CREATE TABLE app_user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    login_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE security_profile (
    security_profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_code TEXT UNIQUE,
    name TEXT NOT NULL,
    permissions_json TEXT NOT NULL DEFAULT '{}',
    is_system INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE user_security_profile (
    user_id INTEGER NOT NULL,
    security_profile_id INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (user_id, security_profile_id),
    FOREIGN KEY (user_id) REFERENCES app_user(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (security_profile_id) REFERENCES security_profile(security_profile_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX idx_user_one_active_security_profile
    ON user_security_profile(user_id) WHERE is_active = 1;

CREATE TABLE user_settings (
    settings_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    active_universe_id INTEGER NOT NULL,
    results_display_mode TEXT NOT NULL DEFAULT 'COMPACT',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES app_user(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (active_universe_id) REFERENCES universe(universe_id) ON DELETE RESTRICT
);

CREATE TABLE source_external (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('METADATA_API', 'EXTERNAL_LINK', 'MANUAL_REFERENCE')),
    base_url TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE universe_source (
    universe_source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    is_available INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
    default_priority INTEGER,
    configuration_text TEXT,
    FOREIGN KEY (universe_id) REFERENCES universe(universe_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id) REFERENCES source_external(source_id) ON DELETE RESTRICT,
    UNIQUE (universe_id, source_id)
);

CREATE INDEX idx_universe_source_available
    ON universe_source(universe_id, is_available, default_priority);

CREATE TABLE user_settings_source_preference (
    settings_id INTEGER NOT NULL,
    universe_source_id INTEGER NOT NULL,
    is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1)),
    preference_rank INTEGER,
    PRIMARY KEY (settings_id, universe_source_id),
    FOREIGN KEY (settings_id) REFERENCES user_settings(settings_id) ON DELETE CASCADE,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT
);

-- The mechanism is closed; its labels are user-editable and not interpreted by SQL.
CREATE TABLE universe_option (
    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    option_kind TEXT NOT NULL CHECK (option_kind IN (
        'SUPPORT', 'POSSESSION_STATUS', 'ACQUISITION_PROJECT',
        'SALE_PROJECT', 'PHYSICAL_STATE', 'DOCUMENT_ROLE'
    )),
    label TEXT NOT NULL,
    normalized_label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (universe_id) REFERENCES universe(universe_id) ON DELETE RESTRICT,
    UNIQUE (universe_id, option_kind, normalized_label)
);

CREATE INDEX idx_universe_option_lookup
    ON universe_option(universe_id, option_kind, is_active, sort_order);

CREATE TABLE entity (
    entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    objective_reference_text TEXT,
    original_name TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (universe_id) REFERENCES universe(universe_id) ON DELETE RESTRICT
);

CREATE INDEX idx_entity_universe_name ON entity(universe_id, normalized_name);

CREATE TABLE location (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    parent_location_id INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (parent_location_id) REFERENCES location(location_id) ON DELETE RESTRICT,
    UNIQUE (parent_location_id, normalized_name)
);

CREATE INDEX idx_location_parent_order
    ON location(parent_location_id, sort_order, normalized_name);

CREATE TABLE media (
    media_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    inventory_reference TEXT UNIQUE,
    support_option_id INTEGER,
    possession_status_option_id INTEGER,
    acquisition_project_option_id INTEGER,
    sale_project_option_id INTEGER,
    physical_state_option_id INTEGER,
    current_location_id INTEGER,
    previous_location_path TEXT,
    physical_order INTEGER,
    entered_on TEXT,
    left_on TEXT,
    maximum_purchase_price_cents INTEGER,
    purchase_price_cents INTEGER,
    estimated_value_cents INTEGER,
    asking_price_cents INTEGER,
    sale_price_cents INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entity(entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (support_option_id) REFERENCES universe_option(option_id) ON DELETE RESTRICT,
    FOREIGN KEY (possession_status_option_id) REFERENCES universe_option(option_id) ON DELETE RESTRICT,
    FOREIGN KEY (acquisition_project_option_id) REFERENCES universe_option(option_id) ON DELETE RESTRICT,
    FOREIGN KEY (sale_project_option_id) REFERENCES universe_option(option_id) ON DELETE RESTRICT,
    FOREIGN KEY (physical_state_option_id) REFERENCES universe_option(option_id) ON DELETE RESTRICT,
    FOREIGN KEY (current_location_id) REFERENCES location(location_id) ON DELETE RESTRICT
);

CREATE INDEX idx_media_entity ON media(entity_id);
CREATE INDEX idx_media_status ON media(possession_status_option_id);
CREATE INDEX idx_media_acquisition ON media(acquisition_project_option_id);
CREATE INDEX idx_media_location ON media(current_location_id);

-- Fully generic per-universe classification mechanism. No classification label is seeded or special-cased.
CREATE TABLE classification (
    classification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    application_scope TEXT NOT NULL CHECK (application_scope IN ('ENTITY', 'MEDIA', 'BOTH')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (universe_id) REFERENCES universe(universe_id) ON DELETE RESTRICT,
    UNIQUE (universe_id, normalized_name)
);

CREATE TABLE classification_value (
    classification_value_id INTEGER PRIMARY KEY AUTOINCREMENT,
    classification_id INTEGER NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (classification_id) REFERENCES classification(classification_id) ON DELETE CASCADE,
    UNIQUE (classification_id, normalized_value)
);

CREATE TABLE entity_classification_attribution (
    entity_id INTEGER NOT NULL,
    classification_value_id INTEGER NOT NULL,
    acquisition_mode TEXT NOT NULL CHECK (acquisition_mode IN ('MANUAL', 'AUTOMATIC', 'MIGRATED_LEGACY')),
    universe_source_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (entity_id, classification_value_id),
    FOREIGN KEY (entity_id) REFERENCES entity(entity_id) ON DELETE CASCADE,
    FOREIGN KEY (classification_value_id) REFERENCES classification_value(classification_value_id) ON DELETE CASCADE,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT
);

CREATE INDEX idx_entity_attr_value
    ON entity_classification_attribution(classification_value_id, entity_id);

CREATE TABLE media_classification_attribution (
    media_id INTEGER NOT NULL,
    classification_value_id INTEGER NOT NULL,
    acquisition_mode TEXT NOT NULL CHECK (acquisition_mode IN ('MANUAL', 'AUTOMATIC', 'MIGRATED_LEGACY')),
    universe_source_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (media_id, classification_value_id),
    FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE,
    FOREIGN KEY (classification_value_id) REFERENCES classification_value(classification_value_id) ON DELETE CASCADE,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT
);

CREATE INDEX idx_media_attr_value
    ON media_classification_attribution(classification_value_id, media_id);

CREATE TABLE user_settings_hidden_classification (
    settings_id INTEGER NOT NULL,
    classification_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (settings_id, classification_id),
    FOREIGN KEY (settings_id) REFERENCES user_settings(settings_id) ON DELETE CASCADE,
    FOREIGN KEY (classification_id) REFERENCES classification(classification_id) ON DELETE RESTRICT
);

CREATE TABLE user_settings_hidden_classification_value (
    settings_id INTEGER NOT NULL,
    classification_value_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (settings_id, classification_value_id),
    FOREIGN KEY (settings_id) REFERENCES user_settings(settings_id) ON DELETE CASCADE,
    FOREIGN KEY (classification_value_id) REFERENCES classification_value(classification_value_id) ON DELETE RESTRICT
);

CREATE TABLE entity_external_reference (
    entity_external_reference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    universe_source_id INTEGER NOT NULL,
    external_id TEXT,
    external_url TEXT,
    last_retrieved_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entity(entity_id) ON DELETE CASCADE,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT,
    UNIQUE (universe_source_id, external_id)
);

CREATE TABLE media_external_reference (
    media_external_reference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL,
    universe_source_id INTEGER NOT NULL,
    external_id TEXT,
    external_url TEXT,
    last_retrieved_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT,
    UNIQUE (universe_source_id, external_id)
);

-- Complementary, non-central information only. Core search/filter/integrity data stays in dedicated columns and tables.
CREATE TABLE entity_information (
    entity_information_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    field_code TEXT NOT NULL,
    value_type TEXT NOT NULL CHECK (value_type IN ('TEXT', 'INTEGER', 'DECIMAL', 'DATE', 'JSON')),
    value_text TEXT,
    value_integer INTEGER,
    value_decimal NUMERIC,
    value_date TEXT,
    value_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entity(entity_id) ON DELETE CASCADE,
    UNIQUE (entity_id, field_code)
);

CREATE TABLE media_information (
    media_information_id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL,
    field_code TEXT NOT NULL,
    value_type TEXT NOT NULL CHECK (value_type IN ('TEXT', 'INTEGER', 'DECIMAL', 'DATE', 'JSON')),
    value_text TEXT,
    value_integer INTEGER,
    value_decimal NUMERIC,
    value_date TEXT,
    value_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE,
    UNIQUE (media_id, field_code)
);

CREATE TABLE entity_information_origin (
    origin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    entity_information_id INTEGER NOT NULL,
    field_code TEXT NOT NULL,
    value_snapshot TEXT,
    universe_source_id INTEGER,
    external_id_snapshot TEXT,
    external_url_snapshot TEXT,
    acquisition_mode TEXT NOT NULL CHECK (acquisition_mode IN ('MANUAL', 'AUTOMATIC', 'MIGRATED_LEGACY')),
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entity(entity_id) ON DELETE CASCADE,
    FOREIGN KEY (entity_information_id) REFERENCES entity_information(entity_information_id) ON DELETE RESTRICT,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT
);

CREATE TABLE media_information_origin (
    origin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL,
    media_information_id INTEGER NOT NULL,
    field_code TEXT NOT NULL,
    value_snapshot TEXT,
    universe_source_id INTEGER,
    external_id_snapshot TEXT,
    external_url_snapshot TEXT,
    acquisition_mode TEXT NOT NULL CHECK (acquisition_mode IN ('MANUAL', 'AUTOMATIC', 'MIGRATED_LEGACY')),
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE,
    FOREIGN KEY (media_information_id) REFERENCES media_information(media_information_id) ON DELETE RESTRICT,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT
);

-- DOCUMENT is a real stored file. Its role and display order belong to each association.
CREATE TABLE document (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    storage_uri TEXT NOT NULL UNIQUE,
    original_file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size_bytes INTEGER,
    checksum_sha256 TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE INDEX idx_document_checksum ON document(checksum_sha256);

CREATE TABLE entity_document (
    entity_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    role_option_id INTEGER,
    display_rank INTEGER NOT NULL DEFAULT 0,
    acquisition_mode TEXT NOT NULL CHECK (acquisition_mode IN ('MANUAL', 'AUTOMATIC', 'MIGRATED_LEGACY')),
    universe_source_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (entity_id, document_id),
    FOREIGN KEY (entity_id) REFERENCES entity(entity_id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES document(document_id) ON DELETE RESTRICT,
    FOREIGN KEY (role_option_id) REFERENCES universe_option(option_id) ON DELETE RESTRICT,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT
);

CREATE TABLE media_document (
    media_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    role_option_id INTEGER,
    display_rank INTEGER NOT NULL DEFAULT 0,
    acquisition_mode TEXT NOT NULL CHECK (acquisition_mode IN ('MANUAL', 'AUTOMATIC', 'MIGRATED_LEGACY')),
    universe_source_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (media_id, document_id),
    FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES document(document_id) ON DELETE RESTRICT,
    FOREIGN KEY (role_option_id) REFERENCES universe_option(option_id) ON DELETE RESTRICT,
    FOREIGN KEY (universe_source_id) REFERENCES universe_source(universe_source_id) ON DELETE RESTRICT
);

CREATE TABLE navigation_state (
    state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    current_screen TEXT NOT NULL,
    selected_media_id INTEGER,
    results_scroll_offset INTEGER,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES app_user(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (selected_media_id) REFERENCES media(media_id) ON DELETE SET NULL
);

-- Migration audit tables. They preserve a row-by-row record; they never alter films.db.
CREATE TABLE migration_batch (
    migration_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('DRY_RUN', 'PENDING_REVIEW', 'COMPLETED', 'ROLLED_BACK'))
);

CREATE TABLE migration_v1_film_map (
    migration_batch_id INTEGER NOT NULL,
    v1_film_id INTEGER NOT NULL,
    v1_disc_id TEXT NOT NULL,
    raw_record_json TEXT NOT NULL,
    entity_id INTEGER,
    media_id INTEGER,
    outcome TEXT NOT NULL CHECK (outcome IN ('MIGRATED', 'MIGRATED_WITH_REVIEW', 'EXCEPTION')),
    rule_code TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (migration_batch_id, v1_film_id),
    FOREIGN KEY (migration_batch_id) REFERENCES migration_batch(migration_batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (entity_id) REFERENCES entity(entity_id) ON DELETE SET NULL,
    FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE SET NULL
);

CREATE TABLE migration_exception (
    migration_exception_id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_batch_id INTEGER NOT NULL,
    v1_film_id INTEGER NOT NULL,
    exception_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'BLOCKING')),
    raw_value TEXT,
    proposed_action TEXT,
    resolution TEXT,
    resolved_at TEXT,
    FOREIGN KEY (migration_batch_id) REFERENCES migration_batch(migration_batch_id) ON DELETE RESTRICT
);

-- Generic consistency triggers. No label or VALUE has special treatment.
CREATE TRIGGER trg_entity_attribution_scope
BEFORE INSERT ON entity_classification_attribution
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM classification_value v
        JOIN classification c ON c.classification_id = v.classification_id
        JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE v.classification_value_id = NEW.classification_value_id
          AND c.application_scope IN ('ENTITY', 'BOTH')
          AND c.universe_id = e.universe_id
    ) THEN RAISE(ABORT, 'Invalid ENTITY classification attribution') END;
END;

CREATE TRIGGER trg_media_attribution_scope
BEFORE INSERT ON media_classification_attribution
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM classification_value v
        JOIN classification c ON c.classification_id = v.classification_id
        JOIN media m ON m.media_id = NEW.media_id
        JOIN entity e ON e.entity_id = m.entity_id
        WHERE v.classification_value_id = NEW.classification_value_id
          AND c.application_scope IN ('MEDIA', 'BOTH')
          AND c.universe_id = e.universe_id
    ) THEN RAISE(ABORT, 'Invalid MEDIA classification attribution') END;
END;

CREATE TRIGGER trg_media_move_requires_previous_path
BEFORE UPDATE OF current_location_id ON media
WHEN OLD.current_location_id IS NOT NULL
 AND NEW.current_location_id IS NOT OLD.current_location_id
 AND (NEW.previous_location_path IS NULL OR trim(NEW.previous_location_path) = '')
BEGIN
    SELECT RAISE(ABORT, 'Previous location path is required before moving a MEDIA');
END;

-- Referential integrity across universe-scoped mechanisms. These triggers only
-- verify structural scope and option kind; no business label is interpreted.
CREATE TRIGGER trg_media_options_insert_scope
BEFORE INSERT ON media
BEGIN
    SELECT CASE WHEN NEW.support_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.support_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'SUPPORT'
    ) THEN RAISE(ABORT, 'Invalid MEDIA support option') END;
    SELECT CASE WHEN NEW.possession_status_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.possession_status_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'POSSESSION_STATUS'
    ) THEN RAISE(ABORT, 'Invalid MEDIA possession status option') END;
    SELECT CASE WHEN NEW.acquisition_project_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.acquisition_project_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'ACQUISITION_PROJECT'
    ) THEN RAISE(ABORT, 'Invalid MEDIA acquisition project option') END;
    SELECT CASE WHEN NEW.sale_project_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.sale_project_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'SALE_PROJECT'
    ) THEN RAISE(ABORT, 'Invalid MEDIA sale project option') END;
    SELECT CASE WHEN NEW.physical_state_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.physical_state_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'PHYSICAL_STATE'
    ) THEN RAISE(ABORT, 'Invalid MEDIA physical state option') END;
END;

CREATE TRIGGER trg_media_options_update_scope
BEFORE UPDATE OF entity_id, support_option_id, possession_status_option_id, acquisition_project_option_id,
                 sale_project_option_id, physical_state_option_id ON media
BEGIN
    SELECT CASE WHEN NEW.support_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.support_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'SUPPORT'
    ) THEN RAISE(ABORT, 'Invalid MEDIA support option') END;
    SELECT CASE WHEN NEW.possession_status_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.possession_status_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'POSSESSION_STATUS'
    ) THEN RAISE(ABORT, 'Invalid MEDIA possession status option') END;
    SELECT CASE WHEN NEW.acquisition_project_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.acquisition_project_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'ACQUISITION_PROJECT'
    ) THEN RAISE(ABORT, 'Invalid MEDIA acquisition project option') END;
    SELECT CASE WHEN NEW.sale_project_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.sale_project_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'SALE_PROJECT'
    ) THEN RAISE(ABORT, 'Invalid MEDIA sale project option') END;
    SELECT CASE WHEN NEW.physical_state_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.physical_state_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'PHYSICAL_STATE'
    ) THEN RAISE(ABORT, 'Invalid MEDIA physical state option') END;
END;

CREATE TRIGGER trg_entity_document_scope
BEFORE INSERT ON entity_document
BEGIN
    SELECT CASE WHEN NEW.role_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.role_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'DOCUMENT_ROLE'
    ) THEN RAISE(ABORT, 'Invalid ENTITY document role') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid ENTITY document source') END;
END;

CREATE TRIGGER trg_media_document_scope
BEFORE INSERT ON media_document
BEGIN
    SELECT CASE WHEN NEW.role_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE o.option_id = NEW.role_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'DOCUMENT_ROLE'
    ) THEN RAISE(ABORT, 'Invalid MEDIA document role') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid MEDIA document source') END;
END;

CREATE TRIGGER trg_entity_external_reference_scope
BEFORE INSERT ON entity_external_reference
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid ENTITY external source') END;
END;

CREATE TRIGGER trg_media_external_reference_scope
BEFORE INSERT ON media_external_reference
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid MEDIA external source') END;
END;

CREATE TRIGGER trg_entity_information_origin_scope
BEFORE INSERT ON entity_information_origin
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM entity_information i
        WHERE i.entity_information_id = NEW.entity_information_id AND i.entity_id = NEW.entity_id AND i.field_code = NEW.field_code
    ) THEN RAISE(ABORT, 'Invalid ENTITY information origin') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid ENTITY information source') END;
END;

CREATE TRIGGER trg_media_information_origin_scope
BEFORE INSERT ON media_information_origin
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM media_information i
        WHERE i.media_information_id = NEW.media_information_id AND i.media_id = NEW.media_id AND i.field_code = NEW.field_code
    ) THEN RAISE(ABORT, 'Invalid MEDIA information origin') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid MEDIA information source') END;
END;

CREATE TRIGGER trg_entity_universe_update_attribution_scope
BEFORE UPDATE OF universe_id ON entity
WHEN NEW.universe_id IS NOT OLD.universe_id
BEGIN
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM entity_classification_attribution a
        JOIN classification_value v ON v.classification_value_id = a.classification_value_id
        JOIN classification c ON c.classification_id = v.classification_id
        WHERE a.entity_id = OLD.entity_id AND (c.universe_id <> NEW.universe_id OR c.application_scope NOT IN ('ENTITY', 'BOTH'))
    ) OR EXISTS (
        SELECT 1 FROM media m
        JOIN media_classification_attribution a ON a.media_id = m.media_id
        JOIN classification_value v ON v.classification_value_id = a.classification_value_id
        JOIN classification c ON c.classification_id = v.classification_id
        WHERE m.entity_id = OLD.entity_id AND (c.universe_id <> NEW.universe_id OR c.application_scope NOT IN ('MEDIA', 'BOTH'))
    ) OR EXISTS (
        SELECT 1 FROM media m
        WHERE m.entity_id = OLD.entity_id AND (
            m.support_option_id IS NOT NULL OR m.possession_status_option_id IS NOT NULL
            OR m.acquisition_project_option_id IS NOT NULL OR m.sale_project_option_id IS NOT NULL
            OR m.physical_state_option_id IS NOT NULL
        )
    ) OR EXISTS (SELECT 1 FROM entity_document d WHERE d.entity_id = OLD.entity_id AND (d.role_option_id IS NOT NULL OR d.universe_source_id IS NOT NULL))
      OR EXISTS (SELECT 1 FROM media_document d JOIN media m ON m.media_id = d.media_id WHERE m.entity_id = OLD.entity_id AND (d.role_option_id IS NOT NULL OR d.universe_source_id IS NOT NULL))
      OR EXISTS (SELECT 1 FROM entity_external_reference r WHERE r.entity_id = OLD.entity_id)
      OR EXISTS (SELECT 1 FROM media_external_reference r JOIN media m ON m.media_id = r.media_id WHERE m.entity_id = OLD.entity_id)
      OR EXISTS (SELECT 1 FROM entity_information_origin o WHERE o.entity_id = OLD.entity_id AND o.universe_source_id IS NOT NULL)
      OR EXISTS (SELECT 1 FROM media_information_origin o JOIN media m ON m.media_id = o.media_id WHERE m.entity_id = OLD.entity_id AND o.universe_source_id IS NOT NULL)
    THEN RAISE(ABORT, 'ENTITY universe change would invalidate classification attributions') END;
END;

CREATE TRIGGER trg_classification_update_attribution_scope
BEFORE UPDATE OF universe_id, application_scope ON classification
BEGIN
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM classification_value v
        JOIN entity_classification_attribution a ON a.classification_value_id = v.classification_value_id
        JOIN entity e ON e.entity_id = a.entity_id
        WHERE v.classification_id = OLD.classification_id
          AND (NEW.universe_id <> e.universe_id OR NEW.application_scope NOT IN ('ENTITY', 'BOTH'))
    ) OR EXISTS (
        SELECT 1 FROM classification_value v
        JOIN media_classification_attribution a ON a.classification_value_id = v.classification_value_id
        JOIN media m ON m.media_id = a.media_id
        JOIN entity e ON e.entity_id = m.entity_id
        WHERE v.classification_id = OLD.classification_id
          AND (NEW.universe_id <> e.universe_id OR NEW.application_scope NOT IN ('MEDIA', 'BOTH'))
    ) THEN RAISE(ABORT, 'CLASSIFICATION change would invalidate attributions') END;
END;

CREATE TRIGGER trg_entity_attribution_update_scope
BEFORE UPDATE OF entity_id, classification_value_id ON entity_classification_attribution
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM classification_value v JOIN classification c ON c.classification_id = v.classification_id
        JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE v.classification_value_id = NEW.classification_value_id
          AND c.application_scope IN ('ENTITY', 'BOTH') AND c.universe_id = e.universe_id
    ) THEN RAISE(ABORT, 'Invalid ENTITY classification attribution') END;
END;

CREATE TRIGGER trg_media_attribution_update_scope
BEFORE UPDATE OF media_id, classification_value_id ON media_classification_attribution
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM classification_value v JOIN classification c ON c.classification_id = v.classification_id
        JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE v.classification_value_id = NEW.classification_value_id
          AND c.application_scope IN ('MEDIA', 'BOTH') AND c.universe_id = e.universe_id
    ) THEN RAISE(ABORT, 'Invalid MEDIA classification attribution') END;
END;

-- The same checks apply when a link is edited after its initial creation.
CREATE TRIGGER trg_entity_document_update_scope
BEFORE UPDATE OF entity_id, role_option_id, universe_source_id ON entity_document
BEGIN
    SELECT CASE WHEN NEW.role_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE o.option_id = NEW.role_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'DOCUMENT_ROLE'
    ) THEN RAISE(ABORT, 'Invalid ENTITY document role') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid ENTITY document source') END;
END;

CREATE TRIGGER trg_media_document_update_scope
BEFORE UPDATE OF media_id, role_option_id, universe_source_id ON media_document
BEGIN
    SELECT CASE WHEN NEW.role_option_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_option o JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE o.option_id = NEW.role_option_id AND o.universe_id = e.universe_id AND o.option_kind = 'DOCUMENT_ROLE'
    ) THEN RAISE(ABORT, 'Invalid MEDIA document role') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid MEDIA document source') END;
END;

CREATE TRIGGER trg_entity_external_reference_update_scope
BEFORE UPDATE OF entity_id, universe_source_id ON entity_external_reference
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid ENTITY external source') END;
END;

CREATE TRIGGER trg_media_external_reference_update_scope
BEFORE UPDATE OF media_id, universe_source_id ON media_external_reference
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid MEDIA external source') END;
END;

CREATE TRIGGER trg_entity_information_origin_update_scope
BEFORE UPDATE OF entity_id, entity_information_id, field_code, universe_source_id ON entity_information_origin
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM entity_information i
        WHERE i.entity_information_id = NEW.entity_information_id AND i.entity_id = NEW.entity_id AND i.field_code = NEW.field_code
    ) THEN RAISE(ABORT, 'Invalid ENTITY information origin') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN entity e ON e.entity_id = NEW.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid ENTITY information source') END;
END;

CREATE TRIGGER trg_media_information_origin_update_scope
BEFORE UPDATE OF media_id, media_information_id, field_code, universe_source_id ON media_information_origin
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM media_information i
        WHERE i.media_information_id = NEW.media_information_id AND i.media_id = NEW.media_id AND i.field_code = NEW.field_code
    ) THEN RAISE(ABORT, 'Invalid MEDIA information origin') END;
    SELECT CASE WHEN NEW.universe_source_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM universe_source s JOIN media m ON m.media_id = NEW.media_id JOIN entity e ON e.entity_id = m.entity_id
        WHERE s.universe_source_id = NEW.universe_source_id AND s.universe_id = e.universe_id AND s.is_available = 1
    ) THEN RAISE(ABORT, 'Invalid MEDIA information source') END;
END;

CREATE TRIGGER trg_entity_information_update_origin_scope
BEFORE UPDATE OF entity_id, field_code ON entity_information
WHEN EXISTS (SELECT 1 FROM entity_information_origin o WHERE o.entity_information_id = OLD.entity_information_id)
BEGIN
    SELECT RAISE(ABORT, 'Cannot change ENTITY information identity while provenance exists');
END;

CREATE TRIGGER trg_media_information_update_origin_scope
BEFORE UPDATE OF media_id, field_code ON media_information
WHEN EXISTS (SELECT 1 FROM media_information_origin o WHERE o.media_information_id = OLD.media_information_id)
BEGIN
    SELECT RAISE(ABORT, 'Cannot change MEDIA information identity while provenance exists');
END;

CREATE TRIGGER trg_universe_option_update_scope
BEFORE UPDATE OF universe_id, option_kind ON universe_option
WHEN EXISTS (
    SELECT 1 FROM media m WHERE m.support_option_id = OLD.option_id OR m.possession_status_option_id = OLD.option_id
       OR m.acquisition_project_option_id = OLD.option_id OR m.sale_project_option_id = OLD.option_id
       OR m.physical_state_option_id = OLD.option_id
) OR EXISTS (SELECT 1 FROM entity_document d WHERE d.role_option_id = OLD.option_id)
  OR EXISTS (SELECT 1 FROM media_document d WHERE d.role_option_id = OLD.option_id)
BEGIN
    SELECT RAISE(ABORT, 'Cannot change an option identity while it is referenced');
END;

CREATE TRIGGER trg_universe_source_update_scope
BEFORE UPDATE OF universe_id, is_available ON universe_source
WHEN EXISTS (SELECT 1 FROM entity_document d WHERE d.universe_source_id = OLD.universe_source_id)
  OR EXISTS (SELECT 1 FROM media_document d WHERE d.universe_source_id = OLD.universe_source_id)
  OR EXISTS (SELECT 1 FROM entity_external_reference r WHERE r.universe_source_id = OLD.universe_source_id)
  OR EXISTS (SELECT 1 FROM media_external_reference r WHERE r.universe_source_id = OLD.universe_source_id)
  OR EXISTS (SELECT 1 FROM entity_information_origin o WHERE o.universe_source_id = OLD.universe_source_id)
  OR EXISTS (SELECT 1 FROM media_information_origin o WHERE o.universe_source_id = OLD.universe_source_id)
BEGIN
    SELECT RAISE(ABORT, 'Cannot change a referenced universe source scope or availability');
END;

-- Initial structural data. No CLASSIFICATION or VALUE is seeded.
INSERT INTO universe (code, name, is_enabled, created_at)
VALUES ('MOVIES', 'Movies', 1, CURRENT_TIMESTAMP);

INSERT INTO app_user (login_name, display_name, password_hash, is_active, created_at, updated_at)
VALUES ('local', 'Utilisateur local', NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO security_profile (profile_code, name, permissions_json, is_system, is_active, created_at, updated_at)
VALUES ('STANDARD', 'Standard', '{}', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO user_security_profile (user_id, security_profile_id, is_active, assigned_at)
SELECT u.user_id, p.security_profile_id, 1, CURRENT_TIMESTAMP
FROM app_user u CROSS JOIN security_profile p
WHERE u.login_name = 'local' AND p.profile_code = 'STANDARD';

INSERT INTO source_external (code, name, source_type, base_url, is_enabled, created_at)
VALUES
    ('TMDB', 'TMDB', 'METADATA_API', 'https://www.themoviedb.org', 1, CURRENT_TIMESTAMP),
    ('ALLOCINE', 'Allociné', 'EXTERNAL_LINK', 'https://www.allocine.fr', 1, CURRENT_TIMESTAMP);

INSERT INTO universe_source (universe_id, source_id, is_available, default_priority)
SELECT u.universe_id, s.source_id, 1,
       CASE s.code WHEN 'TMDB' THEN 1 ELSE 2 END
FROM universe u CROSS JOIN source_external s
WHERE u.code = 'MOVIES';

INSERT INTO user_settings (user_id, active_universe_id, results_display_mode, updated_at)
SELECT au.user_id, u.universe_id, 'COMPACT', CURRENT_TIMESTAMP
FROM app_user au CROSS JOIN universe u
WHERE au.login_name = 'local' AND u.code = 'MOVIES';

INSERT INTO user_settings_source_preference (settings_id, universe_source_id, is_favorite, preference_rank)
SELECT us.settings_id, src.universe_source_id, 1, src.default_priority
FROM user_settings us CROSS JOIN universe_source src;

-- These options are editable examples, not closed lists and not classifications.
INSERT INTO universe_option (universe_id, option_kind, label, normalized_label, sort_order, created_at)
SELECT u.universe_id, x.option_kind, x.label, x.normalized_label, x.sort_order, CURRENT_TIMESTAMP
FROM universe u CROSS JOIN (
    SELECT 'SUPPORT' AS option_kind, 'DVD' AS label, 'dvd' AS normalized_label, 10 AS sort_order
    UNION ALL SELECT 'SUPPORT', 'Blu-ray', 'bluray', 20
    UNION ALL SELECT 'SUPPORT', 'Inconnu', 'inconnu', 99
    UNION ALL SELECT 'POSSESSION_STATUS', 'Présent', 'present', 10
    UNION ALL SELECT 'POSSESSION_STATUS', 'Prêté', 'prete', 20
    UNION ALL SELECT 'POSSESSION_STATUS', 'Vendu', 'vendu', 30
    UNION ALL SELECT 'POSSESSION_STATUS', 'Perdu', 'perdu', 40
    UNION ALL SELECT 'ACQUISITION_PROJECT', 'Souhaité', 'souhaite', 10
    UNION ALL SELECT 'ACQUISITION_PROJECT', 'En commande', 'encommande', 20
    UNION ALL SELECT 'SALE_PROJECT', 'À vendre', 'avendre', 10
    UNION ALL SELECT 'PHYSICAL_STATE', 'Neuf', 'neuf', 10
    UNION ALL SELECT 'PHYSICAL_STATE', 'Bon', 'bon', 20
    UNION ALL SELECT 'PHYSICAL_STATE', 'Usé', 'use', 30
    UNION ALL SELECT 'PHYSICAL_STATE', 'Abîmé', 'abime', 40
    UNION ALL SELECT 'PHYSICAL_STATE', 'Inconnu', 'inconnu', 99
    UNION ALL SELECT 'DOCUMENT_ROLE', 'Jaquette', 'jaquette', 10
    UNION ALL SELECT 'DOCUMENT_ROLE', 'Affiche', 'affiche', 20
    UNION ALL SELECT 'DOCUMENT_ROLE', 'Photo du disque', 'photodisque', 30
    UNION ALL SELECT 'DOCUMENT_ROLE', 'Certificat', 'certificat', 40
    UNION ALL SELECT 'DOCUMENT_ROLE', 'Documentation', 'documentation', 50
) x
WHERE u.code = 'MOVIES';

COMMIT;
