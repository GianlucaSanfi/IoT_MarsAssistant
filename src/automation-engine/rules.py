import pika
import psycopg2
import json

conn = psycopg2.connect(
    host="postgres",
    database="iotdb",
    user="iot",
    password="iot"
)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq')
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
    sensor = data["sensor"]
    value = data["value"]

    cur = conn.cursor()
    cur.execute("SELECT * FROM rules WHERE sensor=%s", (sensor,))
    rules = cur.fetchall()

    for r in rules:

        threshold = r[3]

        if value > threshold:
            print("Rule triggered:", r)

channel.basic_consume(
    queue=queue_name,
    on_message_callback=callback,
    auto_ack=True
)

print("Rule engine started")

channel.start_consuming()