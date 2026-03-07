from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import psycopg2
import pika
import json
import threading
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

clients = []

conn = psycopg2.connect(
    host="postgres",
    database="iotdb",
    user="iot",
    password="iot"
)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


# -------------------
# RULES API
# -------------------

@app.get("/rules")
def get_rules():
    cur = conn.cursor()
    cur.execute("SELECT * FROM rules")
    rows = cur.fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "sensor": r[1],
            "operator": r[2],
            "threshold": r[3],
            "actuator": r[4],
            "action": r[5]
        })
    return result


@app.post("/rules")
async def create_rule(request: Request):
    rule = await request.json()

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO rules(sensor,operator,threshold,actuator,action) VALUES (%s,%s,%s,%s,%s)",
        (rule["sensor"], rule["operator"], rule["threshold"], rule["actuator"], rule["action"])
    )
    conn.commit()
    return {"status":"created"}


@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: int):

    cur = conn.cursor()
    cur.execute("DELETE FROM rules WHERE id=%s", (rule_id,))
    conn.commit()

    return {"status": "deleted"}


# -------------------
# WEBSOCKET
# -------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):

    await ws.accept()
    clients.append(ws)

    try:
        while True:
            await ws.receive_text()
    except:
        clients.remove(ws)


# -------------------
# RABBITMQ SENSOR LISTENER
# -------------------

def rabbit_listener():

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq")
    )

    channel = connection.channel()

    channel.exchange_declare(exchange='iot.events', exchange_type='topic')

    result = channel.queue_declare('', exclusive=True)
    queue_name = result.method.queue

    channel.queue_bind(
        exchange='iot.events',
        queue=queue_name,
        routing_key="sensor.#"
    )

    def callback(ch, method, properties, body):

        data = json.loads(body)

        for client in clients:
            try:
                import asyncio
                asyncio.run(client.send_text(json.dumps(data)))
            except:
                pass

    channel.basic_consume(
        queue=queue_name,
        on_message_callback=callback,
        auto_ack=True
    )

    channel.start_consuming()


threading.Thread(target=rabbit_listener, daemon=True).start()