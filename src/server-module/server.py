import pika
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

    time.sleep(5)