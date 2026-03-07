import pika
import requests
import json
import time
import threading
import sseclient

RABBIT_HOST = "rabbitmq"
API_HOST = "http://host.docker.internal:8080"

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBIT_HOST)
)

channel = connection.channel()

channel.exchange_declare(
    exchange='iot.events',
    exchange_type='topic'
)

# -------------------
# SSE SENSOR STREAM
# -------------------

def listen_sse(topic):

    url = f"{API_HOST}/api/telemetry/stream/{topic}"

    print("Connecting SSE:", url)

    response = requests.get(url, stream=True)

    client = sseclient.SSEClient(response)

    for event in client.events():

        data = json.loads(event.data)

        print("SSE sensor:", data)

        channel.basic_publish(
            exchange='iot.events',
            routing_key=f"sensor.{topic}",
            body=json.dumps(data)
        )


# -------------------
# REST POLLING SENSORS
# -------------------

def poll_sensors():

    url = f"{API_HOST}/api/sensors"

    while True:

        try:
            response = requests.get(url)
            sensors = response.json()

            for sensor in sensors:

                print("Polled sensor:", sensor)

                channel.basic_publish(
                    exchange='iot.events',
                    routing_key=f"sensor.{sensor['type']}",
                    body=json.dumps(sensor)
                )

        except Exception as e:
            print("Polling error:", e)

        time.sleep(10)


# -------------------
# ACTUATOR COMMANDS
# -------------------

def actuator_callback(ch, method, properties, body):

    command = json.loads(body)

    actuator_id = command["actuator_id"]

    url = f"{API_HOST}/api/actuators/{actuator_id}"

    print("Sending actuator command:", command)

    requests.post(url, json=command)


def listen_actuators():

    result = channel.queue_declare('', exclusive=True)
    queue_name = result.method.queue

    channel.queue_bind(
        exchange='iot.events',
        queue=queue_name,
        routing_key="actuator.command"
    )

    channel.basic_consume(
        queue=queue_name,
        on_message_callback=actuator_callback,
        auto_ack=True
    )

    channel.start_consuming()


# -------------------
# THREAD START
# -------------------

threading.Thread(target=listen_sse, args=("temperature",)).start()
threading.Thread(target=poll_sensors).start()
threading.Thread(target=listen_actuators).start()

print("Server module started")

while True:
    time.sleep(100)
""" import pika
import json
import time
import random

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq')
)

channel = connection.channel()
channel.exchange_declare(exchange='iot.events', exchange_type='topic')

while True:

    sensor_data = {
        "sensor": "temperature",
        "value": random.randint(20, 35)
    }

    channel.basic_publish(
        exchange='iot.events',
        routing_key='sensor.temperature',
        body=json.dumps(sensor_data)
    )

    print("Sent:", sensor_data)

    time.sleep(5) """