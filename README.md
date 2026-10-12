# NOC Syslog Inteligente

**Versión:** MVP v0.2.0  
**Proyecto académico:** Administración y Gestión de Redes

## 1. Descripción del proyecto

NOC Syslog Inteligente es una aplicación web desarrollada con Python y Flask para apoyar la supervisión y gestión de eventos de red. Permite consultar eventos Syslog, administrar dispositivos y gestionar incidentes desde una interfaz web.

## 2. Objetivo

Desarrollar un prototipo para centralizar información de eventos de red y facilitar su consulta y seguimiento mediante un panel web.

## 3. Tecnologías utilizadas

- Python
- Flask
- SQLite
- HTML y CSS
- JavaScript

## 4. Funcionalidades

- Panel principal de supervisión.
- Inventario de dispositivos de red.
- Consulta y filtrado de eventos Syslog, según las funcionalidades implementadas.
- Gestión y seguimiento de incidentes.
- Consola simulada con comandos de referencia.
- Consulta de configuraciones de referencia para Cisco, Fortinet y Huawei.

**Limitaciones:** La consola es simulada y no ejecuta comandos en equipos reales. Las configuraciones por fabricante son material de referencia. Las funciones de inteligencia artificial no deben considerarse implementadas hasta que estén desarrolladas y probadas.

## 5. Estructura del proyecto

- `app.py`: aplicación web Flask.
- `database.py`: funciones de acceso a la base de datos.
- `schema.sql`: estructura de las tablas.
- `syslog_receiver.py`: receptor de mensajes Syslog.
- `Templates/`: plantillas HTML.
- `Static/`: recursos estáticos de la interfaz.
- `Data/`: ubicación de la base de datos local.
- `requirements.txt`: dependencias de Python.
- `.gitignore`: archivos y carpetas excluidos de Git.

## 6. Requisitos

- Python 3.
- Git, si se desea clonar el repositorio.
- Puerto UDP 5514 disponible para probar el receptor Syslog.

## 7. Instalación y ejecución en Windows

### Paso 1. Abrir la carpeta del proyecto

Abre PowerShell en la carpeta `NOC-Syslog-Inteligente`.

### Paso 2. Crear el entorno virtual

Si todavía no existe, ejecuta:

```powershell
python -m venv .venv
```

### Paso 3. Instalar las dependencias

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Paso 4. Iniciar la aplicación web

```powershell
.\.venv\Scripts\python.exe .\app.py
```

Abre en el navegador:

http://127.0.0.1:5000/

Para detener el servidor, presiona `Ctrl + C` en la terminal.

### Paso 5. Iniciar el receptor Syslog

Si deseas probar el receptor, abre una segunda terminal en la carpeta del proyecto y ejecuta:

```powershell
.\.venv\Scripts\python.exe .\syslog_receiver.py
```

El receptor utiliza el puerto UDP 5514, de acuerdo con la configuración del proyecto.

## 8. Base de datos

El proyecto utiliza SQLite para almacenar información persistente. La ruta configurada es `Data/noc_syslog.db`.

Para una instalación nueva, verifica que la base de datos y sus tablas se inicialicen correctamente antes de utilizar la aplicación.
