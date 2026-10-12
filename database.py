import sqlite3
from pathlib import Path

# Carpeta donde se almacenará la base de datos
DATA_DIR = Path("data")
DATABASE_PATH = DATA_DIR / "noc_syslog.db"


def initialize_database():
    """Crea la base de datos y sus tablas."""

    # Crear la carpeta data si no existe
    DATA_DIR.mkdir(exist_ok=True)

    # Conectar con SQLite
    connection = sqlite3.connect(DATABASE_PATH)

    # Activar las relaciones entre tablas
    connection.execute("PRAGMA foreign_keys = ON;")

    # Leer el modelo de datos
    schema = Path("schema.sql").read_text(encoding="utf-8")

    # Crear las tablas definidas en schema.sql
    connection.executescript(schema)

    # Guardar los cambios
    connection.commit()

    # Cerrar la conexión
    connection.close()

    print(f"Base de datos creada correctamente: {DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()