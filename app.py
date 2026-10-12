import ipaddress
import sqlite3
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-only-change-before-deployment"

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "Data" / "noc_syslog.db"

VALID_STATUSES = ("activo", "inactivo", "mantenimiento")


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def validate_device_form():
    """Obtiene y valida los datos enviados por el formulario."""
    device = {
        "name": request.form.get("name", "").strip(),
        "ip_address": request.form.get("ip_address", "").strip(),
        "manufacturer": request.form.get("manufacturer", "").strip(),
        "device_type": request.form.get("device_type", "").strip(),
        "status": request.form.get("status", "activo").strip(),
        "location": request.form.get("location", "").strip(),
        "notes": request.form.get("notes", "").strip(),
    }

    if not all(
        [
            device["name"],
            device["ip_address"],
            device["manufacturer"],
            device["device_type"],
        ]
    ):
        return None, "Completa todos los campos obligatorios."

    try:
        ipaddress.ip_address(device["ip_address"])
    except ValueError:
        return (
            None,
            "La dirección IP no es válida. "
            "Introduce una dirección IPv4 o IPv6 correcta.",
        )

    if device["status"] not in VALID_STATUSES:
        return None, "El estado seleccionado no es válido."

    return device, None


@app.route("/")
def home():
    with get_connection() as connection:
        devices = connection.execute(
            "SELECT * FROM devices ORDER BY id DESC"
        ).fetchall()

    return render_template("index.html", devices=devices)


@app.route("/devices", methods=["POST"])
def create_device():
    device, error = validate_device_form()

    if error:
        flash(error, "error")
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
                    device["name"],
                    device["ip_address"],
                    device["manufacturer"],
                    device["device_type"],
                    device["status"],
                    device["location"] or None,
                    device["notes"] or None,
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


@app.route("/devices/<int:device_id>/edit", methods=["GET", "POST"])
def edit_device(device_id):
    with get_connection() as connection:
        device = connection.execute(
            "SELECT * FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()

    if device is None:
        flash("El dispositivo solicitado no existe.", "error")
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("edit_device.html", device=device)

    updated_device, error = validate_device_form()

    if error:
        flash(error, "error")
        return redirect(url_for("edit_device", device_id=device_id))

    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE devices
                SET name = ?,
                    ip_address = ?,
                    manufacturer = ?,
                    device_type = ?,
                    status = ?,
                    location = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    updated_device["name"],
                    updated_device["ip_address"],
                    updated_device["manufacturer"],
                    updated_device["device_type"],
                    updated_device["status"],
                    updated_device["location"] or None,
                    updated_device["notes"] or None,
                    device_id,
                ),
            )

        flash("Dispositivo actualizado correctamente.", "success")
        return redirect(url_for("home"))

    except sqlite3.IntegrityError:
        flash(
            "No se pudo actualizar el dispositivo. "
            "Comprueba que la dirección IP no pertenezca a otro dispositivo.",
            "error",
        )
        return redirect(url_for("edit_device", device_id=device_id))


@app.route("/devices/<int:device_id>/delete", methods=["POST"])
def delete_device(device_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM devices WHERE id = ?",
            (device_id,),
        )

        if cursor.rowcount == 0:
            flash("El dispositivo no existe o ya fue eliminado.", "error")
        else:
            flash("Dispositivo eliminado correctamente.", "success")

    return redirect(url_for("home"))


if __name__ == "__main__":
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {DATABASE_PATH}. "
            "Ejecuta primero database.py."
        )

    app.run(debug=True)