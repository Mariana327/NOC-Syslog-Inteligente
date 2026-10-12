
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>NOC Syslog Inteligente</h1>
    <p>MVP v0.2.0 - Fase 1</p>
    <p>Servidor Flask funcionando correctamente.</p>
    """

if __name__ == "__main__":
    app.run(debug=True)
