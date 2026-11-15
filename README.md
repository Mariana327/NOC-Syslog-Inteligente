# NOC Syslog Inteligente

**Versión del proyecto:** v1.0.0  
**Tipo:** Proyecto académico – Administración y Gestión de Redes  
**Repositorio:** https://github.com/Mariana327/NOC-Syslog-Inteligente  
**Aplicación desplegada:** https://noc-syslog-inteligente.onrender.com/

## 1. Descripción general

NOC Syslog Inteligente es una aplicación web desarrollada con Python y Flask para apoyar la supervisión de eventos de red y la gestión de incidentes desde un entorno de Centro de Operaciones de Red (NOC).

La plataforma centraliza la recepción, clasificación, almacenamiento y consulta de eventos Syslog. También incorpora herramientas para el seguimiento de incidentes, notificaciones y autorizaciones mediante Telegram, además de un módulo demostrativo para validar comandos asociados a equipos de distintos fabricantes.

El proyecto tiene un alcance académico y demostrativo. Las funciones deben interpretarse de acuerdo con las capacidades descritas en este documento; en particular, el Gestor SSH funciona mediante simulación y no administra dispositivos físicos.

## 2. Objetivos

- Centralizar la recepción y consulta de eventos Syslog.
- Clasificar los eventos de acuerdo con los niveles de severidad Syslog (0 a 7).
- Facilitar la visualización y búsqueda de eventos mediante filtros.
- Apoyar el registro, asignación y seguimiento de incidentes.
- Enviar notificaciones y gestionar solicitudes de autorización mediante Telegram.
- Demostrar la validación de comandos y el registro de auditoría en un entorno SSH simulado.
- Aplicar principios de seguridad, trazabilidad y supervisión humana.

## 3. Funcionalidades principales

### Supervisión de eventos Syslog
- Recepción de eventos mediante una API HTTP.
- Validación de solicitudes de ingreso mediante un token configurado en el servidor.
- Clasificación por severidad Syslog de 0 a 7.
- Almacenamiento y consulta de registros.
- Visualización en el dashboard y filtros por severidad, dirección IP de origen y fecha.
- Generación de eventos de demostración para las pruebas.

### Inventario de dispositivos
- Registro y consulta de dispositivos.
- Edición y eliminación de registros del inventario.
- Organización de información de equipos de red.

### Gestión de incidentes
- Consulta y seguimiento de incidentes asociados a eventos.
- Asignación y confirmación del responsable.
- Registro de causa, diagnóstico, acción correctiva y resultado de verificación.
- Solicitud de autorización para marcar una resolución como completada mediante Telegram.
- Actualización del estado y cierre del incidente según el flujo implementado.

### Notificaciones y autorizaciones con Telegram
- Envío de notificaciones para eventos de severidad configurada, incluidos los niveles 0 a 3.
- Envío de solicitudes de autorización relacionadas con la resolución de incidentes.
- Validación de la interacción de autorización mediante el bot configurado.

### Gestor SSH simulado
- Inventario demostrativo de equipos Cisco, Fortinet y Huawei.
- Perfiles de usuario de demostración.
- Validación de comandos de consulta permitidos y rechazo de comandos restringidos.
- Respuestas de terminal predefinidas según el fabricante y el comando.
- Registro de solicitudes y resultados en una auditoría.

**Importante:** el Gestor SSH no establece conexiones SSH reales, no autentica contra equipos físicos y no ejecuta cambios de configuración en routers, switches o firewalls. Las respuestas son simuladas y tienen fines demostrativos. Los perfiles disponibles tampoco representan un sistema empresarial integral de gestión de identidades y permisos.

## 4. Tecnologías utilizadas

- **Python 3:** lenguaje principal.
- **Flask:** framework para la aplicación web y sus rutas.
- **SQLite:** almacenamiento de datos.
- **HTML y CSS:** estructura y presentación de la interfaz.
- **JavaScript:** interactividad y comunicación con el servidor.
- **Telegram Bot API:** notificaciones y autorizaciones.
- **Git y GitHub:** control de versiones y repositorio del código.
- **Render:** despliegue de la aplicación web.

## 5. Arquitectura general

El flujo principal de supervisión se resume así:

1. Un evento Syslog es recibido mediante la API o generado para demostración.
2. El servidor valida la solicitud y procesa la información del evento.
3. El evento se clasifica según su severidad.
4. La información se almacena en SQLite.
5. El dashboard permite consultar los registros y aplicar filtros.
6. Cuando corresponde, se genera una notificación mediante Telegram y se puede iniciar el flujo de gestión de incidentes.
7. Las solicitudes realizadas en el Gestor SSH simulado se validan y registran en su auditoría, sin conexión con equipos físicos.

## 6. Estructura del proyecto

Entre los principales archivos y directorios se encuentran:

- `app.py`: aplicación Flask, rutas y lógica del servidor.
- `database.py`: inicialización y acceso a la base de datos.
- `schema.sql`: definición de tablas y estructura de almacenamiento.
- `requirements.txt`: dependencias de Python.
- `Templates/`: plantillas HTML.
- `static/css/`: hojas de estilo.
- `static/js/`: scripts JavaScript.
- `Data/`: ubicación configurada para la base de datos local.
- `syslog_receiver.py`: componente receptor Syslog disponible en el proyecto, cuando se utilice ese modo de recepción.

La estructura exacta puede ampliarse a medida que evolucione el proyecto.

## 7. Requisitos

Para ejecutar el proyecto localmente se requiere:

- Windows, Linux o macOS.
- Python 3.
- Git.
- Acceso a una terminal.
- Navegador web actualizado.
- Conexión a Internet para instalar dependencias y utilizar los servicios externos.

Para habilitar las notificaciones y autorizaciones de Telegram se deben configurar las credenciales correspondientes.

## 8. Instalación y ejecución local

Clonar el repositorio:

```bash
git clone https://github.com/Mariana327/NOC-Syslog-Inteligente.git
cd NOC-Syslog-Inteligente
```

Crear el entorno virtual en Windows:

```powershell
python -m venv .venv
```

Instalar las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Configurar las variables de entorno necesarias para el entorno local. Entre ellas se encuentran:

- `SYSLOG_INGEST_TOKEN`: token utilizado para proteger el ingreso de eventos a la API.
- `TELEGRAM_BOT_TOKEN`: token del bot de Telegram.
- `TELEGRAM_CHAT_ID`: identificador del chat configurado para las notificaciones.

Los valores reales deben mantenerse privados y no deben incluirse en el repositorio.

Iniciar la aplicación:

```powershell
.\.venv\Scripts\python.exe .\app.py
```

Abrir en el navegador:

`http://127.0.0.1:5000/`

## 9. API de recepción de eventos

La aplicación dispone de un endpoint para recibir eventos Syslog mediante solicitudes HTTP:

`POST /api/syslog`

La solicitud debe incluir el encabezado de autenticación `X-Syslog-Token`, con el valor configurado en `SYSLOG_INGEST_TOKEN` en el servidor. No se debe publicar el token real en ejemplos, capturas ni documentación.

La respuesta HTTP depende del resultado de la validación y del procesamiento de la solicitud. En las pruebas realizadas se verificó la aceptación de solicitudes autorizadas y el rechazo de solicitudes con token inválido.

## 10. Despliegue

La aplicación se encuentra publicada en Render:

https://noc-syslog-inteligente.onrender.com/

El código fuente se administra en GitHub. Las variables de entorno requeridas deben configurarse de forma segura en el servicio de despliegue y no almacenarse directamente en el repositorio.

La persistencia de SQLite en el entorno alojado depende de la configuración de almacenamiento de Render. Para conservar datos de manera duradera en un entorno de producción se debe configurar almacenamiento persistente y establecer copias de seguridad.

## 11. Seguridad y uso responsable

- Los tokens y credenciales deben almacenarse como variables de entorno.
- Los eventos recibidos deben tratarse como datos no confiables.
- Las operaciones sensibles requieren revisión y autorización humana.
- La validación de comandos del Gestor SSH corresponde a una demostración y no habilita ejecución remota.
- Las notificaciones y autorizaciones dependen de la configuración y disponibilidad de Telegram.
- Las recomendaciones automatizadas no sustituyen la evaluación de personal autorizado.

## 12. Limitaciones conocidas

- El Gestor SSH es completamente simulado y no establece conexiones con infraestructura física.
- Los equipos y perfiles del Gestor SSH son datos de demostración.
- Las respuestas de terminal son simuladas y no reflejan el estado real de dispositivos.
- El proyecto no constituye una plataforma certificada de seguridad ni una solución empresarial de monitoreo a gran escala.
- La conservación de datos en el despliegue depende de la configuración de almacenamiento del servicio de alojamiento.
- Las capacidades de inteligencia artificial deben limitarse a las funciones efectivamente implementadas y verificadas.

## 13. Referencias técnicas

- Flask: https://flask.palletsprojects.com/
- Python: https://docs.python.org/3/
- SQLite: https://www.sqlite.org/docs.html
- Telegram Bot API: https://core.telegram.org/bots/api
- Render: https://render.com/docs
- GitHub Docs: https://docs.github.com/
- RFC 5424 – The Syslog Protocol: https://www.rfc-editor.org/rfc/rfc5424
- RFC 3164 – The BSD Syslog Protocol: https://www.rfc-editor.org/rfc/rfc3164

---

**NOC Syslog Inteligente v1.0.0**  
Proyecto académico de supervisión de eventos Syslog y gestión de incidentes de red.
