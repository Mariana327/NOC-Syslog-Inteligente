
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ip_address TEXT NOT NULL UNIQUE,
    manufacturer TEXT NOT NULL,
    device_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'activo'
        CHECK (status IN ('activo', 'inactivo', 'mantenimiento')),
    location TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS syslog_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,
    source_ip TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    facility INTEGER
        CHECK (facility IS NULL OR facility BETWEEN 0 AND 23),
    severity INTEGER NOT NULL
        CHECK (severity BETWEEN 0 AND 7),
    message TEXT NOT NULL,
    raw_message TEXT,
    FOREIGN KEY (device_id)
        REFERENCES devices(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_syslog_events_received_at
    ON syslog_events(received_at);

CREATE INDEX IF NOT EXISTS idx_syslog_events_severity
    ON syslog_events(severity);

CREATE INDEX IF NOT EXISTS idx_syslog_events_source_ip
    ON syslog_events(source_ip);
    
-- Tabla para la gestión de incidentes del NOC.
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity INTEGER NOT NULL
        CHECK (severity BETWEEN 0 AND 7),
    status TEXT NOT NULL DEFAULT 'abierto'
        CHECK (status IN ('abierto', 'en_progreso', 'resuelto', 'cerrado')),
    source_ip TEXT,
    syslog_event_id INTEGER,
    assigned_to TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    FOREIGN KEY (syslog_event_id)
        REFERENCES syslog_events(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_status
    ON incidents(status);

CREATE INDEX IF NOT EXISTS idx_incidents_severity
    ON incidents(severity);

CREATE INDEX IF NOT EXISTS idx_incidents_created_at
    ON incidents(created_at);
