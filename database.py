
import sqlite3
from pathlib import Path

# Carpeta raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent

# Carpeta y archivo de la base de datos
DATA_DIR = BASE_DIR / "Data"
DATABASE_PATH = DATA_DIR / "noc_syslog.db"

# Archivo que define las tablas
SCHEMA_PATH = BASE_DIR / "schema.sql"


def initialize_database():
    """Crea las tablas sin eliminar los datos existentes."""

    # Crear la carpeta si no existe
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Conectar con la base de datos del proyecto
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        # Activar las relaciones entre tablas
        connection.execute("PRAGMA foreign_keys = ON;")

        # Leer el esquema SQL
        schema = SCHEMA_PATH.read_text(encoding="utf-8-sig")

        # Crear las tablas e índices que falten
        connection.executescript(schema)

        # Verificar si existe el campo de confirmación
        columns = [
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(incidents)"
            ).fetchall()
        ]

        if "responsible_confirmed" not in columns:
            connection.execute(
                """
                ALTER TABLE incidents
                ADD COLUMN responsible_confirmed INTEGER NOT NULL DEFAULT 0
                """
            )

                # Campos para el registro y autorización de resolución
        resolution_columns = {
            "resolution_cause": "TEXT",
            "resolution_diagnosis": "TEXT",
            "corrective_action": "TEXT",
            "verification_result": "TEXT",
            "resolution_submitted_at": "TEXT",
            "resolution_approval_token": "TEXT",
            "resolution_approved_at": "TEXT",
            "resolution_approved_by": "TEXT",
        }

        for column_name, column_type in resolution_columns.items():
            if column_name not in columns:
                connection.execute(
                    f"ALTER TABLE incidents "
                    f"ADD COLUMN {column_name} {column_type}"
                )

        # Confirmar los cambios
        connection.commit()

        print(f"Base de datos inicializada correctamente: {DATABASE_PATH}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()

