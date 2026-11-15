
document.addEventListener("submit", async function (event) {
    const form = event.target;

    if (!form.matches("#ssh-command-form")) {
        return;
    }

    event.preventDefault();

    const terminal = document.getElementById("ssh-terminal-result");
    const button = form.querySelector('button[type="submit"]');

    button.disabled = true;
    terminal.textContent = "Validando comando simulado...";

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: {
                "Accept": "application/json"
            }
        });

        const data = await response.json();

        terminal.textContent = data.result || "No se recibió una respuesta.";

        if (!response.ok) {
            console.warn("Comando rechazado:", data);
        }

    } catch (error) {
        terminal.textContent =
            "No fue posible completar la validación del comando.";

        console.error("Error en Gestor SSH:", error);

    } finally {
        button.disabled = false;
    }
});
