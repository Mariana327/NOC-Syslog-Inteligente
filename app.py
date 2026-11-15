import os
import secrets
import ipaddress
import sqlite3
import requests
import hmac
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import CSRFProtect
app = Flask(__name__, template_folder="Templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("La variable de entorno SECRET_KEY no está configurada.")
csrf = CSRFProtect(app)

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "Data" / "noc_syslog.db"

VALID_STATUSES = ("activo", "inactivo", "mantenimiento")
MAX_SYSLOG_MESSAGE_BYTES = 8192
def send_telegram_alert(source_ip, severity, message, event_id):
    """Envía una alerta Syslog a Telegram cuando corresponde."""

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    print("Token disponible:", bool(bot_token), "| Chat ID disponible:", bool(chat_id))

    if not bot_token or not chat_id:
        print("Telegram no está configurado.")
        return False

    severity_names = {
        0: "EMERGENCIA",
        1: "ALERTA",
        2: "CRÍTICO",
        3: "ERROR",
    }

    if severity not in severity_names:
        return False

    text = (
        "🚨 ALERTA NOC SYSLOG INTELIGENTE\n\n"
        f"Evento: #{event_id}\n"
        f"IP de origen: {source_ip}\n"
        f"Severidad: {severity} - {severity_names[severity]}\n"
        f"Mensaje: {message[:1000]}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
            },
            timeout=5,
        )

        response.raise_for_status()

        result = response.json()

        if result.get("ok"):
            print(f"Alerta Telegram enviada para el evento #{event_id}.")
            return True

        print("Telegram no confirmó el envío.")
        return False

    except requests.RequestException as error:
        print(f"Error al enviar alerta a Telegram: {error}")
        return False

def send_telegram_resolution_request(
    incident_id,
    title,
    source_ip,
    severity,
    responsible,
    cause,
    diagnosis,
    corrective_action,
    verification_result,
    approval_token,
):
    """Envía a Telegram una solicitud de aprobación de resolución."""

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Telegram no está configurado para resoluciones.")
        return None

    text = (
        "📋 SOLICITUD DE RESOLUCIÓN - NOC\n\n"
        f"Incidente: #{incident_id}\n"
        f"Título: {title}\n"
        f"IP de origen: {source_ip or 'No disponible'}\n"
        f"Severidad: {severity}\n"
        f"Responsable: {responsible}\n\n"
        f"CAUSA IDENTIFICADA:\n{cause}\n\n"
        f"DIAGNÓSTICO:\n{diagnosis}\n\n"
        f"ACCIÓN CORRECTIVA:\n{corrective_action}\n\n"
        f"VERIFICACIÓN:\n{verification_result}\n\n"
        "Revisa el registro antes de autorizar la resolución."
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {
                    "inline_keyboard": [[
                        {
                            "text": "Autorizar como resuelto",
                            "callback_data": (
                                f"approve_resolution|{incident_id}|{approval_token}"
                            ),
                        }
                    ]]
                },
            },
            timeout=10,
        )

        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            print(
                f"Solicitud de resolución enviada para el incidente #{incident_id}."
            )
            return result["result"]["message_id"]

        print("Telegram no confirmó el envío de la resolución.")
        return None

    except requests.RequestException as error:
        print(f"Error al enviar solicitud de resolución: {error}")
        return None
    
def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    from database import initialize_database
    initialize_database()


init_db()

@app.route("/api/syslog", methods=["POST"])
@csrf.exempt
def receive_syslog():
    expected_token = os.environ.get("SYSLOG_INGEST_TOKEN", "")
    provided_token = request.headers.get("X-Syslog-Token", "")

    if not expected_token or not secrets.compare_digest(
        provided_token, expected_token
    ):
        return jsonify({"error": "No autorizado"}), 401

    if request.content_length is not None:
        if request.content_length > MAX_SYSLOG_MESSAGE_BYTES:
            return jsonify({
                "error": "El mensaje Syslog supera el tamaño máximo permitido."
            }), 413
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Se requiere un JSON válido"}), 400

    source_ip = str(data.get("source_ip", "")).strip()
    raw_message = str(data.get("message", "")).strip()
    if len(raw_message.encode("utf-8")) > MAX_SYSLOG_MESSAGE_BYTES:
        return jsonify({
            "error": "El mensaje Syslog supera el tamaño máximo permitido."
        }), 413
    try:
        source_ip = str(ipaddress.ip_address(source_ip))
    except ValueError:
        return jsonify({"error": "La IP de origen no es válida"}), 400

    if not raw_message.startswith("<") or ">" not in raw_message:
        return jsonify({"error": "El mensaje Syslog no es válido"}), 400

    try:
        end = raw_message.index(">")
        priority = int(raw_message[1:end])

        if not 0 <= priority <= 191:
            raise ValueError

        facility = priority // 8
        severity = priority % 8
        message = raw_message[end + 1:].strip()

        if not message:
            raise ValueError

    except ValueError:
        return jsonify({"error": "Prioridad Syslog no válida"}), 400

    with get_connection() as connection:
        device = connection.execute(
            "SELECT id FROM devices WHERE ip_address = ?",
            (source_ip,),
        ).fetchone()

        device_id = device["id"] if device else None

        cursor = connection.execute(
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

        event_id = cursor.lastrowid

        incident_id = None

        if severity in (0, 1, 2):

            if severity in (0, 1):
                suggested_responsible = "Administrador NOC"
            else:
                suggested_responsible = "Analista de redes"

            incident_cursor = connection.execute(
                """
                INSERT INTO incidents (
                    title,
                    description,
                    severity,
                    status,
                    source_ip,
                    syslog_event_id,
                    assigned_to,
                    responsible_confirmed
                )
                VALUES (?, ?, ?, 'abierto', ?, ?, ?, 0)
                """,
                (
                    f"Incidente automático - Severidad {severity}",
                    message,
                    severity,
                    source_ip,
                    event_id,
                    suggested_responsible,
                ),
            )

            incident_id = incident_cursor.lastrowid

    send_telegram_alert(
        source_ip,
        severity,
        message,
        event_id,
    )

    return jsonify({
        "status": "ok",
        "message": "Evento Syslog registrado",
        "event_id": event_id,
        "severity": severity,
        "incident_created": incident_id is not None,
        "incident_id": incident_id,
    }), 201


@app.route("/generar-eventos-demo", methods=["POST"])
def generate_demo_events():
    """Genera eventos Syslog ficticios para demostración."""

    facility = 1

    demo_events = {
        0: "Fallo total simulado del dispositivo de red.",
        1: "Posible intento de acceso no autorizado.",
        2: "Interrupción crítica de una interfaz.",
        3: "Error en la conexión de red.",
        4: "Uso elevado de CPU.",
        5: "Cambio de configuración.",
        6: "Inicio de sesión de usuario.",
        7: "Información de diagnóstico.",
    }

    selected_severity = request.form.get("severity", "todas")

    if selected_severity == "todas":
        events_to_generate = list(demo_events.items())

    elif selected_severity.isdigit() and int(selected_severity) in demo_events:
        severity = int(selected_severity)
        events_to_generate = [(severity, demo_events[severity])]

    else:
        flash("La severidad seleccionada no es válida.", "error")
        return redirect(url_for("home") + "#seccion-eventos")

    source_ip = "192.168.100.10"
    created_events = []

    connection = get_connection()

    try:
        for severity, message in events_to_generate:
            simulated_message = "[SIMULADO] " + message
            priority = facility * 8 + severity
            raw_message = f"<{priority}>{simulated_message}"

            cursor = connection.execute(
                """
                INSERT INTO syslog_events
                    (device_id, source_ip, facility, severity, message, raw_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    None,
                    source_ip,
                    facility,
                    severity,
                    simulated_message,
                    raw_message,
                ),
            )

            event_id = cursor.lastrowid

            if severity in (0, 1, 2):

                if severity in (0, 1):
                    suggested_responsible = "Administrador NOC"
                else:
                    suggested_responsible = "Analista de redes"

                connection.execute(
                    """
                    INSERT INTO incidents (
                        title,
                        description,
                        severity,
                        status,
                        source_ip,
                        syslog_event_id,
                        assigned_to,
                        responsible_confirmed
                    )
                    VALUES (?, ?, ?, 'abierto', ?, ?, ?, 0)
                    """,
                    (
                        f"Incidente automático simulado - Severidad {severity}",
                        simulated_message,
                        severity,
                        source_ip,
                        event_id,
                        suggested_responsible,
                    ),
                )

            created_events.append(
                (cursor.lastrowid, severity, simulated_message)
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    for event_id, severity, message in created_events:
        send_telegram_alert(
            source_ip,
            severity,
            message,
            event_id,
        )

    total = len(created_events)

    flash(
        f"Se generaron {total} evento(s) Syslog simulado(s) correctamente.",
        "success",
    )

    return redirect(url_for("home") + "#vista-eventos")

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

@app.route("/incidents/<int:incident_id>")
def incident_detail(incident_id):
    with get_connection() as connection:
        incident = connection.execute(
            "SELECT * FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()

    if incident is None:
        flash("El incidente solicitado no existe.", "error")
        return redirect(url_for("home") + "#seccion-incidentes")

    status_messages = {
        "abierto": "Incidente registrado. Está pendiente de revisión y asignación de acciones.",
        "en_progreso": "El incidente está siendo atendido. Se debe continuar con el diagnóstico y la solución.",
        "resuelto": "Se ha registrado una solución. Se recomienda verificar que el servicio funcione correctamente.",
        "cerrado": "La gestión del incidente ha finalizado. El caso queda disponible para consulta.",
    }

    return render_template(
        "incidente_detalle.html",
        incident=incident,
        status_message=status_messages.get(incident["status"], ""),
    )

@app.route(
    "/incidents/<int:incident_id>/resolution",
    methods=["POST"]
)
def submit_incident_resolution(incident_id):

    cause = request.form.get("resolution_cause", "").strip()
    diagnosis = request.form.get("resolution_diagnosis", "").strip()
    corrective_action = request.form.get("corrective_action", "").strip()
    verification_result = request.form.get("verification_result", "").strip()

    fields = [
        cause,
        diagnosis,
        corrective_action,
        verification_result,
    ]

    if not all(fields):
        return jsonify({
            "success": False,
            "message": "Completa todos los campos del registro."
        }), 400

    with get_connection() as connection:
        incident = connection.execute(
            """
            SELECT *
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,),
        ).fetchone()

        if incident is None:
            return jsonify({
                "success": False,
                "message": "El incidente no existe."
            }), 404

        if (
            incident["status"] != "en_progreso"
            or incident["responsible_confirmed"] != 1
        ):
            return jsonify({
                "success": False,
                "message": "El incidente debe tener un responsable confirmado y estar en progreso."
            }), 400

        approval_token = secrets.token_hex(12)

        connection.execute(
            """
            UPDATE incidents
            SET resolution_cause = ?,
                resolution_diagnosis = ?,
                corrective_action = ?,
                verification_result = ?,
                resolution_submitted_at = CURRENT_TIMESTAMP,
                resolution_approval_token = ?
            WHERE id = ?
            """,
            (
                cause,
                diagnosis,
                corrective_action,
                verification_result,
                approval_token,
                incident_id,
            ),
        )

    message_id = send_telegram_resolution_request(
        incident_id=incident_id,
        title=incident["title"],
        source_ip=incident["source_ip"],
        severity=incident["severity"],
        responsible=incident["assigned_to"],
        cause=cause,
        diagnosis=diagnosis,
        corrective_action=corrective_action,
        verification_result=verification_result,
        approval_token=approval_token,
    )

    if message_id is None:
        return jsonify({
            "success": False,
            "message": "No se pudo enviar la solicitud a Telegram. El registro quedó guardado; puedes intentar enviarlo nuevamente."
        }), 502

    return jsonify({
        "success": True,
        "message": "Registro guardado y enviado a Telegram para tu autorización."
    })

@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():

    webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token", ""
    )

    if (
        not webhook_secret
        or not hmac.compare_digest(received_secret, webhook_secret)
    ):
        return jsonify({"ok": False}), 403
    authorized_user_id = os.environ.get("TELEGRAM_AUTHORIZED_USER_ID")

    if not authorized_user_id:
        return jsonify({"ok": False}), 500

    update = request.get_json(silent=True) or {}
    callback = update.get("callback_query")

    if not callback:
        return jsonify({"ok": True})

    telegram_user_id = str(
        callback.get("from", {}).get("id", "")
    )

    callback_id = callback.get("id")
    callback_data = callback.get("data", "")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if telegram_user_id != authorized_user_id:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id,
                "text": "No tienes autorización para aprobar.",
                "show_alert": True,
            },
            timeout=5,
        )
        return jsonify({"ok": True})

    parts = callback_data.split("|")

    if len(parts) != 3 or parts[0] != "approve_resolution":
        return jsonify({"ok": True})

    incident_id = parts[1]
    approval_token = parts[2]

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE incidents
            SET status = 'resuelto',
                resolved_at = CURRENT_TIMESTAMP,
                resolution_approved_at = CURRENT_TIMESTAMP,
                resolution_approved_by = ?,
                resolution_approval_token = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'en_progreso'
              AND resolution_approval_token = ?
            """,
            (
                telegram_user_id,
                incident_id,
                approval_token,
            ),
        )

    if cursor.rowcount == 1:
        callback_message = "Resolución autorizada. Incidente marcado como resuelto."
    else:
        callback_message = "La solicitud no es válida o ya fue procesada."

    requests.post(
        f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
        json={
            "callback_query_id": callback_id,
            "text": callback_message,
            "show_alert": True,
        },
        timeout=5,
    )

    return jsonify({"ok": True})

@app.route("/incidents/<int:incident_id>/responsible", methods=["POST"])
def confirm_incident_responsible(incident_id):

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE incidents
            SET responsible_confirmed = 1,
                status = 'en_progreso',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND assigned_to IS NOT NULL
              AND assigned_to != ''
            """,
            (incident_id,),
        )

        if cursor.rowcount == 0:
            flash(
                "No se pudo confirmar el responsable. "
                "Verifica que el incidente tenga una asignación.",
                "error",
            )
            return redirect(
    url_for("incident_detail", incident_id=incident_id)
    + "#asignacion-responsable")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
         with get_connection() as connection:
            incident = connection.execute(
                """
                SELECT assigned_to, status, responsible_confirmed
                FROM incidents
                WHERE id = ?
                """,
                (incident_id,),
            ).fetchone()

        return jsonify({
            "success": True,
            "assigned_to": incident["assigned_to"],
            "status": incident["status"],
            "responsible_confirmed": incident["responsible_confirmed"],
            "message": "Responsable confirmado. El incidente está en progreso.",
        })

    flash(
        "Responsable confirmado correctamente. "
        "El incidente ahora está en progreso.",
        "success",
    )

    return redirect(
        url_for("incident_detail", incident_id=incident_id)
        + "#asignacion-responsable"
    )

@app.route("/incidents/<int:incident_id>/reassign", methods=["POST"])
def reassign_incident_responsible(incident_id):
    responsible = request.form.get("assigned_to", "").strip()

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    allowed_responsibles = [
        "Administrador NOC",
        "Analista de redes",
        "Técnico de infraestructura",
        "Técnico de redes",
    ]

    if responsible not in allowed_responsibles:
        if is_ajax:
            return jsonify({
                "success": False,
                "message": "Selecciona un responsable válido.",
            }), 400

        flash("Selecciona un responsable válido.", "error")
        return redirect(url_for(
            "incident_detail",
            incident_id=incident_id
        ))

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE incidents
            SET assigned_to = ?,
                responsible_confirmed = 0,
                status = 'abierto',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (responsible, incident_id),
        )

        if cursor.rowcount == 0:
            if is_ajax:
                return jsonify({
                    "success": False,
                    "message": "El incidente no existe.",
                }), 404

            flash("El incidente no existe.", "error")
            return redirect(url_for("home") + "#seccion-incidentes")

        incident = connection.execute(
            """
            SELECT assigned_to, status, responsible_confirmed
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,),
        ).fetchone()

    if is_ajax:
        return jsonify({
            "success": True,
            "assigned_to": incident["assigned_to"],
            "status": incident["status"],
            "responsible_confirmed": incident["responsible_confirmed"],
            "message": "Nuevo responsable asignado. Pendiente de confirmación.",
        })

    flash(
        "Nuevo responsable asignado. Está pendiente de confirmación.",
        "success",
    )

    return redirect(
        url_for("incident_detail", incident_id=incident_id)
        + "#asignacion-responsable"
    )

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
                    AS other_events,
                SUM(CASE WHEN severity = 0 THEN 1 ELSE 0 END) AS severity_0,
                SUM(CASE WHEN severity = 1 THEN 1 ELSE 0 END) AS severity_1,
                SUM(CASE WHEN severity = 2 THEN 1 ELSE 0 END) AS severity_2,
                SUM(CASE WHEN severity = 3 THEN 1 ELSE 0 END) AS severity_3,
                SUM(CASE WHEN severity = 4 THEN 1 ELSE 0 END) AS severity_4,
                SUM(CASE WHEN severity = 5 THEN 1 ELSE 0 END) AS severity_5,
                SUM(CASE WHEN severity = 6 THEN 1 ELSE 0 END) AS severity_6,
                SUM(CASE WHEN severity = 7 THEN 1 ELSE 0 END) AS severity_7
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
    if request.args.get("embedded") == "1":
        return render_template("consola_contenido.html", comandos=comandos)

    return render_template("consola.html", comandos=comandos)


@app.route("/configuraciones")
def configuraciones():
    fabricantes = {
    "Cisco": {
        "descripcion": "Comandos de administración, supervisión y diagnóstico para routers y switches Cisco.",
        "categorias": [
            {
                "nombre": "Información general",
                "comandos": [
                    {
                        "nombre": "Versión del sistema",
                        "comando": "show version",
                        "descripcion": "Consulta la versión del IOS, modelo, tiempo de actividad y memoria."
                    },
                    {
                        "nombre": "Configuración activa",
                        "comando": "show running-config",
                        "descripcion": "Muestra la configuración que está ejecutándose actualmente."
                    },
                    {
                        "nombre": "Inventario de hardware",
                        "comando": "show inventory",
                        "descripcion": "Consulta los componentes y módulos instalados."
                    }
                ]
            },
            {
                "nombre": "Interfaces y conectividad",
                "comandos": [
                    {
                        "nombre": "Resumen de interfaces IP",
                        "comando": "show ip interface brief",
                        "descripcion": "Muestra las direcciones IP y el estado de las interfaces."
                    },
                    {
                        "nombre": "Detalle de interfaces",
                        "comando": "show interfaces",
                        "descripcion": "Consulta estadísticas, errores y estado de las interfaces."
                    },
                    {
                        "nombre": "Tabla ARP",
                        "comando": "show ip arp",
                        "descripcion": "Muestra las asociaciones entre direcciones IP y MAC."
                    }
                ]
            },
            {
                "nombre": "Enrutamiento y VLAN",
                "comandos": [
                    {
                        "nombre": "Tabla de rutas",
                        "comando": "show ip route",
                        "descripcion": "Muestra las rutas conocidas por el dispositivo."
                    },
                    {
                        "nombre": "Resumen de VLAN",
                        "comando": "show vlan brief",
                        "descripcion": "Consulta las VLAN configuradas y sus puertos asociados."
                    },
                    {
                        "nombre": "Vecinos OSPF",
                        "comando": "show ip ospf neighbor",
                        "descripcion": "Muestra los vecinos detectados mediante OSPF."
                    }
                ]
            },
            {
                "nombre": "Registros y Syslog",
                "comandos": [
                    {
                        "nombre": "Registros del sistema",
                        "comando": "show logging",
                        "descripcion": "Consulta los mensajes de registro almacenados."
                    },
                    {
                        "nombre": "Configuración Syslog",
                        "comando": "show running-config | include logging",
                        "descripcion": "Consulta las líneas de configuración relacionadas con logging."
                    }
                ]
            }
        ]
    },

    "Fortinet": {
        "descripcion": "Comandos de administración y diagnóstico para dispositivos FortiGate.",
        "categorias": [
            {
                "nombre": "Información general",
                "comandos": [
                    {
                        "nombre": "Información del sistema",
                        "comando": "get system status",
                        "descripcion": "Consulta versión de FortiOS, modelo y tiempo de actividad."
                    },
                    {
                        "nombre": "Información de hardware",
                        "comando": "get hardware status",
                        "descripcion": "Consulta información del hardware del dispositivo."
                    }
                ]
            },
            {
                "nombre": "Interfaces y conectividad",
                "comandos": [
                    {
                        "nombre": "Configuración de interfaces",
                        "comando": "show system interface",
                        "descripcion": "Muestra la configuración de las interfaces de red."
                    },
                    {
                        "nombre": "Estado de interfaces",
                        "comando": "diagnose netlink interface list",
                        "descripcion": "Consulta información y estado de las interfaces."
                    },
                    {
                        "nombre": "Tabla ARP",
                        "comando": "get system arp",
                        "descripcion": "Muestra las asociaciones ARP conocidas."
                    }
                ]
            },
            {
                "nombre": "Enrutamiento y seguridad",
                "comandos": [
                    {
                        "nombre": "Tabla de rutas",
                        "comando": "get router info routing-table all",
                        "descripcion": "Consulta las rutas disponibles en el dispositivo."
                    },
                    {
                        "nombre": "Políticas de firewall",
                        "comando": "show firewall policy",
                        "descripcion": "Muestra las políticas de firewall configuradas."
                    },
                    {
                        "nombre": "Sesiones activas",
                        "comando": "diagnose sys session list",
                        "descripcion": "Consulta las sesiones de tráfico activas."
                    }
                ]
            },
            {
                "nombre": "Registros y Syslog",
                "comandos": [
                    {
                        "nombre": "Configuración Syslog",
                        "comando": "show log syslogd setting",
                        "descripcion": "Consulta los parámetros de configuración del envío Syslog."
                    },
                    {
                        "nombre": "Configuración de registro",
                        "comando": "get log syslogd setting",
                        "descripcion": "Muestra los parámetros actuales del servicio Syslog."
                    }
                ]
            }
        ]
    },

    "Huawei": {
        "descripcion": "Comandos de administración y diagnóstico para routers y switches Huawei VRP.",
        "categorias": [
            {
                "nombre": "Información general",
                "comandos": [
                    {
                        "nombre": "Versión del sistema",
                        "comando": "display version",
                        "descripcion": "Consulta la versión del software y el modelo del equipo."
                    },
                    {
                        "nombre": "Configuración actual",
                        "comando": "display current-configuration",
                        "descripcion": "Muestra la configuración activa del dispositivo."
                    },
                    {
                        "nombre": "Estado del equipo",
                        "comando": "display device",
                        "descripcion": "Consulta el estado de los componentes del dispositivo."
                    }
                ]
            },
            {
                "nombre": "Interfaces y conectividad",
                "comandos": [
                    {
                        "nombre": "Resumen de interfaces IP",
                        "comando": "display ip interface brief",
                        "descripcion": "Muestra las direcciones IP y el estado de las interfaces."
                    },
                    {
                        "nombre": "Detalle de interfaces",
                        "comando": "display interface",
                        "descripcion": "Consulta estadísticas y estado de las interfaces."
                    },
                    {
                        "nombre": "Tabla ARP",
                        "comando": "display arp",
                        "descripcion": "Muestra las asociaciones entre direcciones IP y MAC."
                    }
                ]
            },
            {
                "nombre": "Enrutamiento y VLAN",
                "comandos": [
                    {
                        "nombre": "Tabla de rutas",
                        "comando": "display ip routing-table",
                        "descripcion": "Consulta las rutas conocidas por el equipo."
                    },
                    {
                        "nombre": "Resumen de VLAN",
                        "comando": "display vlan",
                        "descripcion": "Muestra las VLAN existentes y su información."
                    },
                    {
                        "nombre": "Vecinos OSPF",
                        "comando": "display ospf peer",
                        "descripcion": "Consulta los vecinos OSPF detectados."
                    }
                ]
            },
            {
                "nombre": "Registros y Syslog",
                "comandos": [
                    {
                        "nombre": "Registros del sistema",
                        "comando": "display logbuffer",
                        "descripcion": "Consulta los mensajes almacenados en el búfer de registros."
                    },
                    {
                        "nombre": "Configuración de información",
                        "comando": "display info-center",
                        "descripcion": "Consulta la configuración del servicio de información y registros."
                    }
                ]
            }
        ]
    }
}

    fabricante_seleccionado = request.args.get("fabricante", "")

    if fabricante_seleccionado not in fabricantes:
        fabricante_seleccionado = ""

    if request.args.get("embedded") == "1":
        return render_template(
            "configuraciones_contenido.html",
            fabricantes=fabricantes,
            fabricante_seleccionado=fabricante_seleccionado,
        )

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
    if request.args.get("embedded") == "1":
        return render_template(
            "politicas_ia_contenido.html",
            politicas=politicas,
        )
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