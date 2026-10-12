import sqlite3
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-only-change-before-deployment"

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "Data" / "noc_syslog.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@app.route("/")
def home():
    with get_connection() as connection:
        devices = connection.execute(
            "SELECT * FROM devices ORDER BY id DESC"
        ).fetchall()

    return render_template("index.html", devices=devices)


@app.route("/devices", methods=["POST"])
def create_device():
    name = request.form.get("name", "").strip()
    ip_address = request.form.get("ip_address", "").strip()
    manufacturer = request.form.get("manufacturer", "").strip()
    device_type = request.form.get("device_type", "").strip()
    status = request.form.get("status", "activo").strip()
    location = request.form.get("location", "").strip()
    notes = request.form.get("notes", "").strip()

    if not all([name, ip_address, manufacturer, device_type]):
        flash("Completa todos los campos obligatorios.", "error")
        return redirect(url_for("home"))

    if status not in ("activo", "inactivo", "mantenimiento"):
        flash("El estado seleccionado no es válido.", "error")
        return redirect(url_for("home"))

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO devices
                    (name, ip_address, manufacturer, device_type,
                     status, location, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    ip_address,
                    manufacturer,
                    device_type,
                    status,
                    location or None,
                    notes or None,
                ),
            )
        flash("Dispositivo registrado correctamente.", "success")

    except sqlite3.IntegrityError:
        flash(
            "No se pudo registrar el dispositivo. "
            "Comprueba que la dirección IP no esté registrada.",
            "error",
        )

    return redirect(url_for("home"))


if __name__ == "__main__":
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {DATABASE_PATH}. "
            "Ejecuta primero database.py."
        )

    app.run(debug=True)
