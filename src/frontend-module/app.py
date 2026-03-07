from fastapi import FastAPI
import psycopg2

app = FastAPI()

conn = psycopg2.connect(
    host="postgres",
    database="iotdb",
    user="iot",
    password="iot"
)

@app.get("/rules")
def get_rules():
    cur = conn.cursor()
    cur.execute("SELECT * FROM rules")
    rows = cur.fetchall()
    return rows


@app.post("/rules")
def create_rule(sensor: str, operator: str, value: int, actuator: str, action: str):

    cur = conn.cursor()

    cur.execute(
        "INSERT INTO rules (sensor, operator, threshold, actuator, action) VALUES (%s,%s,%s,%s,%s)",
        (sensor, operator, value, actuator, action)
    )

    conn.commit()

    return {"status": "rule created"}


@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: int):

    cur = conn.cursor()
    cur.execute("DELETE FROM rules WHERE id=%s", (rule_id,))
    conn.commit()

    return {"deleted": rule_id}