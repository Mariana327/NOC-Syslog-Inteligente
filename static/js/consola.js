
const comandosPermitidos = {
    "show version":
        "Consulta simulada de la versión del dispositivo.",

    "show ip interface brief":
        "Consulta simulada del estado de las interfaces.",

    "show logging":
        "Consulta simulada de los registros Syslog."
};

const comandosBloqueados = {
    "configure terminal":
        "Bloqueado: intenta acceder al modo de configuración.",

    "reload":
        "Bloqueado: puede reiniciar el dispositivo.",

    "write erase":
        "Bloqueado: puede borrar la configuración almacenada.",

    "shutdown":
        "Bloqueado: puede deshabilitar una interfaz."
};

function seleccionar(comando) {
    const entrada = document.getElementById("entrada-consola");

    if (entrada) {
        entrada.value = comando;
    }
}

document.addEventListener("submit", function(evento) {
    const formulario = evento.target;

    if (!formulario.matches("#formulario-consola")) {
        return;
    }

    evento.preventDefault();

    const entrada = document.getElementById("entrada-consola");
    const lineaComando = document.getElementById("comando-consola");
    const respuesta = document.getElementById("respuesta-consola");

    if (!entrada || !lineaComando || !respuesta) {
        return;
    }

    const comando = entrada.value.trim().toLowerCase();

    lineaComando.textContent = "NOC-SIMULADO> " + comando;

    respuesta.classList.remove(
        "comando-permitido",
        "comando-bloqueado"
    );

    if (!comando) {
        respuesta.textContent = "BLOQUEADO: ingresa un comando.";
        respuesta.classList.add("comando-bloqueado");
        return;
    }

    if (Object.prototype.hasOwnProperty.call(
        comandosBloqueados, comando
    )) {
        respuesta.textContent = comandosBloqueados[comando];
        respuesta.classList.add("comando-bloqueado");
        return;
    }

    if (Object.prototype.hasOwnProperty.call(
        comandosPermitidos, comando
    )) {
        respuesta.textContent =
            "PERMITIDO (SIMULACIÓN): " +
            comandosPermitidos[comando] +
            " No se consultó ningún dispositivo real.";

        respuesta.classList.add("comando-permitido");
        return;
    }

    respuesta.textContent =
        "BLOQUEADO: el comando no está en la lista autorizada. " +
        "No se ejecutó ninguna acción.";

    respuesta.classList.add("comando-bloqueado");
});
