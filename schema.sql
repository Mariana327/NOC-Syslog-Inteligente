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
