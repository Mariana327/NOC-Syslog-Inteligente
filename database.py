
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
