
import ipaddress
import socket
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "Data" / "noc_syslog.db"

SYSLOG_HOST = "0.0.0.0"
SYSLOG_PORT = 5514


def parse_syslog(message):
    """Extrae la severidad y la facility de un mensaje Syslog estándar."""
    message = message.strip()

    if not message.startswith("<") or ">" not in message:
        return None

    try:
        end = message.index(">")
        priority = int(message[1:end])

        if not 0 <= priority <= 191:
            return None

        facility = priority // 8
        severity = priority % 8

        return facility, severity, message[end + 1:].strip()

    except (ValueError, IndexError):
        return None


def save_event(source_ip, facility, severity, message, raw_message):
    """Guarda el evento Syslog en SQLite."""
    try:
        source_ip = str(ipaddress.ip_address(source_ip))
    except ValueError:
        return

    with sqlite3.connect(DATABASE_PATH, timeout=5) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        device = connection.execute(
            "SELECT id FROM devices WHERE ip_address = ?",
            (source_ip,),
        ).fetchone()

        device_id = device[0] if device else None

        connection.execute(
            """
            INSERT INTO syslog_events
                (device_id, source_ip, facility, severity, message, raw_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                source_ip,
                facility,
                severity,
                message,
                raw_message,
            ),
        )


def start_receiver():
    """Escucha mensajes Syslog por UDP y los almacena."""
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {DATABASE_PATH}"
        )

    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        server.bind((SYSLOG_HOST, SYSLOG_PORT))
        print(f"Receptor Syslog escuchando en UDP {SYSLOG_PORT}")
        print("Presiona Ctrl+C para detenerlo.")

        while True:
            data, address = server.recvfrom(8192)
            raw_message = data.decode("utf-8", errors="replace").strip()

            parsed = parse_syslog(raw_message)

            if parsed is None:
                print(f"Mensaje Syslog no válido desde {address[0]}")
                continue

            facility, severity, message = parsed

            save_event(
                address[0],
                facility,
                severity,
                message,
                raw_message,
            )

            print(
                f"Evento guardado | IP: {address[0]} "
                f"| Severidad: {severity} | Mensaje: {message}"
            )

    except KeyboardInterrupt:
        print("\nReceptor Syslog detenido.")

    finally:
        server.close()


if __name__ == "__main__":
    start_receiver()
