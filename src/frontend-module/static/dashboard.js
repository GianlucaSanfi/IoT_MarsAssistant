const ws = new WebSocket(`ws://${location.host}/ws`);

const sensors = {};

window.onload = () => {
    loadRules();
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    sensors[data.type] = data.value;

    render();
};

function render(){
    const div = document.getElementById("sensors");
    div.innerHTML = "";

    for(const key in sensors){
        div.innerHTML += `
            <div class="card">
                <h3>${key}</h3>
                <div class="sensor-value">${sensors[key]}</div>
            </div>
        `;
    }
}

async function createRule() {
    const rule = {
        sensor: document.getElementById("sensor").value,
        operator: document.getElementById("operator").value,
        threshold: parseInt(document.getElementById("threshold").value),
        actuator: document.getElementById("actuator").value,
        action: document.getElementById("action").value
    };

    await fetch("/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rule)
    });

    loadRules(); // <-- refresh the list after creation
}