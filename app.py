import ipaddress
import sqlite3
from pathlib import Path
from datetime import datetime

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

@app.route("/incidents/<int:incident_id>/status", methods=["POST"])
def update_incident_status(incident_id):
    status = request.form.get("status", "").strip()

    valid_statuses = ("abierto", "en_progreso", "resuelto", "cerrado")

    if status not in valid_statuses:
        flash("El estado seleccionado no es válido.", "error")
        return redirect(url_for("home"))

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE incidents
            SET status = ?,
                updated_at = CURRENT_TIMESTAMP,
                resolved_at = CASE
                    WHEN ? = 'resuelto' THEN CURRENT_TIMESTAMP
                    WHEN ? = 'cerrado' THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END
            WHERE id = ?
            """,
            (status, status, status, incident_id),
        )

        if cursor.rowcount == 0:
            flash("El incidente no existe.", "error")
        else:
            flash("Estado del incidente actualizado correctamente.", "success")

    return redirect(url_for("home") + "#seccion-incidentes")

@app.route("/incidents", methods=["POST"])
def create_incident():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    severity_value = request.form.get("severity", "").strip()
    source_ip = request.form.get("source_ip", "").strip()
    assigned_to = request.form.get("assigned_to", "").strip()

    if not title or not description:
        flash("El título y la descripción del incidente son obligatorios.", "error")
        return redirect(url_for("home"))

    try:
        severity = int(severity_value)
        if severity not in range(8):
            raise ValueError
    except ValueError:
        flash("La severidad debe ser un número entre 0 y 7.", "error")
        return redirect(url_for("home"))

    if source_ip:
        try:
            ipaddress.ip_address(source_ip)
        except ValueError:
            flash("La dirección IP del incidente no es válida.", "error")
            return redirect(url_for("home"))

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO incidents (
                title,
                description,
                severity,
                source_ip,
                assigned_to
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                severity,
                source_ip or None,
                assigned_to or None,
            ),
        )

    flash("Incidente registrado correctamente.", "success")
    return redirect(url_for("home"))

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
                INSERT INTO devices (
                    name,
                    ip_address,
                    manufacturer,
                    device_type,
                    status,
                    location,
                    notes
                )
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



@app.route("/")
def home():
    severity = request.args.get("severity", "").strip()
    source_ip = request.args.get("source_ip", "").strip()
    event_date = request.args.get("event_date", "").strip()

    query = """
        SELECT id, source_ip, received_at, facility, severity, message
        FROM syslog_events
        WHERE 1 = 1
    """
    params = []

    if severity in [str(i) for i in range(8)]:
        query += " AND severity = ?"
        params.append(int(severity))
    else:
        severity = ""

    if source_ip:
        query += " AND source_ip LIKE ?"
        params.append(f"%{source_ip}%")

    if event_date:
        try:
            datetime.strptime(event_date, "%Y-%m-%d")
            query += " AND date(received_at) = date(?)"
            params.append(event_date)
        except ValueError:
            event_date = ""

    query += " ORDER BY id DESC LIMIT 50"

    with get_connection() as connection:
        devices = connection.execute(
            "SELECT * FROM devices ORDER BY id DESC"
        ).fetchall()

        syslog_events = connection.execute(
            query, params
        ).fetchall()

        event_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN severity BETWEEN 0 AND 2 THEN 1 ELSE 0 END)
                    AS critical,
                SUM(CASE WHEN severity = 3 THEN 1 ELSE 0 END)
                    AS errors,
                SUM(CASE WHEN severity BETWEEN 4 AND 7 THEN 1 ELSE 0 END)
                    AS other_events
            FROM syslog_events
            """
        ).fetchone()

        incident_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'abierto' THEN 1 ELSE 0 END) AS abiertos,
                SUM(CASE WHEN status = 'en_progreso' THEN 1 ELSE 0 END) AS en_progreso,
                SUM(CASE WHEN status = 'resuelto' THEN 1 ELSE 0 END) AS resueltos,
                SUM(CASE WHEN status = 'cerrado' THEN 1 ELSE 0 END) AS cerrados
            FROM incidents
            """
        ).fetchone()
        
        incident_status = request.args.get("incident_status", "").strip()
        incident_severity = request.args.get("incident_severity", "").strip()

        valid_statuses = ("abierto", "en_progreso", "resuelto", "cerrado")
        valid_severities = tuple(str(level) for level in range(8))

        filters = []
        params = []

        if incident_status in valid_statuses:
            filters.append("status = ?")
            params.append(incident_status)
        else:
            incident_status = ""

        if incident_severity in valid_severities:
            filters.append("severity = ?")
            params.append(int(incident_severity))
        else:
            incident_severity = ""

        query = "SELECT * FROM incidents"

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY id DESC LIMIT 50"

        incidents = connection.execute(query, params).fetchall()

    return render_template(
        "index.html",
        devices=devices,
        syslog_events=syslog_events,
        event_stats=event_stats,
        incidents=incidents,
        incident_stats=incident_stats,
        selected_severity=severity,
        selected_source_ip=source_ip,
        selected_event_date=event_date,
    )

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


@app.route("/consola")
def consola_simulada():
    comandos = [
        {
            "comando": "show version",
            "descripcion": "Consultar información de versión del equipo",
        },
        {
            "comando": "show interfaces status",
            "descripcion": "Consultar el estado de las interfaces",
        },
        {
            "comando": "show logging",
            "descripcion": "Consultar registros del sistema",
        },
    ]
    return render_template("consola.html", comandos=comandos)


@app.route("/configuraciones")
def configuraciones():
    fabricantes = {
        "Cisco": {
            "descripcion": "Ejemplo de consulta de Syslog para equipos Cisco.",
            "comando": "show logging",
        },
        "Fortinet": {
            "descripcion": "Ejemplo de consulta de registros en FortiGate.",
            "comando": "get log syslogd setting",
        },
        "Huawei": {
            "descripcion": "Ejemplo de consulta de información de registros.",
            "comando": "display logbuffer",
        },
    }
    return render_template(
        "configuraciones.html",
        fabricantes=fabricantes,
    )


@app.route("/panel")
def panel():
    return render_template("panel.html")

@app.route("/politicas-ia")
def politicas_ia():
    politicas = [
        {
            "numero": 1,
            "titulo": "Supervisión humana",
            "descripcion": (
                "Las recomendaciones generadas por inteligencia artificial "
                "deben ser evaluadas por el administrador de red antes de "
                "tomar decisiones que puedan afectar la infraestructura."
            ),
        },
        {
            "numero": 2,
            "titulo": "Protección de datos",
            "descripcion": (
                "Se debe evitar la exposición de contraseñas, claves de "
                "acceso, tokens y otra información sensible durante el "
                "procesamiento de eventos y el uso de herramientas de IA."
            ),
        },
        {
            "numero": 3,
            "titulo": "Autorización de acciones",
            "descripcion": (
                "La inteligencia artificial no debe ejecutar cambios en "
                "la configuración de los dispositivos de red sin la "
                "autorización explícita de un usuario autorizado."
            ),
        },
        {
            "numero": 4,
            "titulo": "Validación de resultados",
            "descripcion": (
                "Las alertas, clasificaciones y recomendaciones generadas "
                "por IA son orientativas y deben contrastarse con los "
                "registros disponibles en el sistema."
            ),
        },
        {
            "numero": 5,
            "titulo": "Registro y trazabilidad",
            "descripcion": (
                "Se debe procurar conservar evidencia de las "
                "recomendaciones generadas y de las decisiones tomadas "
                "por los administradores."
            ),
        },
        {
            "numero": 6,
            "titulo": "Uso responsable y transparencia",
            "descripcion": (
                "El sistema debe distinguir entre los eventos registrados, "
                "las reglas de clasificación aplicadas y las recomendaciones "
                "generadas por inteligencia artificial."
            ),
        },
    ]

    return render_template(
        "politicas_ia.html",
        politicas=politicas,
    )

if __name__ == "__main__":
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {DATABASE_PATH}. "
            "Ejecuta primero database.py."
        )

    app.run(debug=True)