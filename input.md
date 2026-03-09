# MARS ASSISTANT — Mars Environment Automation Platform

## System Overview

MARS ASSISTANT is a distributed automation platform for real-time monitoring and control of a Mars habitat environment. The system ingests heterogeneous sensor data from both REST-polled devices and asynchronous telemetry streams, normalizes it into a unified internal event format, evaluates automation rules, and exposes a real-time dashboard for habitat monitoring and control.

The platform is built on an event-driven architecture using RabbitMQ as the message broker. Ingestion, processing, and presentation are handled by separate services, each running in its own Docker container.

---

## User Stories

### Sensors

1. As a user, I want to click on a sensor widget to open a dedicated detail view showing the current state, metrics, and recent log, so that I can monitor a specific environmental parameter in depth.
2. As a user, I want to view all sensors' states in a unified dashboard with live updates, so that I can have a complete overview of the Mars habitat environment at a glance.
3. As a user, I want to be notified when a sensor status is "warning", so that I can react promptly to dangerous conditions.

### Actuators

4. As a user, I want to view each actuator's current state (ON/OFF) in a dedicated card widget with real-time updates, last change time, and trigger source, so that I always know the actual state of the system.
5. As a user, I want to view all actuators' states in a unified dashboard where each device has its own card with live status indicators, so that I can monitor and manage the entire system from a single screen.
6. As a user, I want to toggle an actuator's state by directly interacting with its widget, so that I can manually intervene on the environment without navigating to a separate settings page.
7. As a user, I want to see the last time an actuator state changed and what triggered the change (manual command or automation rule), so that I can understand recent interventions on the system.
8. As a user, I want to receive a visual confirmation when I manually toggle an actuator, so that I know my command was received by the system.

### Automations

9. As a user, I want to create an automation rule using a simple if-then interface (e.g., if temperature > 30°C → turn on fan), so that I can automate environmental control without writing code.
10. As a user, I want to edit an existing automation rule, so that I can adapt the system's behaviour as mission parameters change.
11. As a user, I want to delete an automation rule, so that I can remove obsolete logic and keep the system clean.
12. As a user, I want to view a list of all automation rules with their current status (active/disabled), so that I can have a clear picture of what logic is running.
13. As a user, I want to disable an automation rule without deleting it, so that I can temporarily suspend its behaviour and re-enable it later when needed.
14. As a user, I want to see when an automation rule was last triggered and what action it performed (e.g., "cooling_fan set ON"), so that I can verify if the rule is behaving as intended.

### General

15. As a user, I want to see the overall system connection status in the top bar, so that I always know if the platform is live or offline.

---

## Devices

### REST Sensors (polled every 10 seconds)

| Sensor ID | Schema |
|---|---|
| `greenhouse_temperature` | rest.scalar.v1 |
| `entrance_humidity` | rest.scalar.v1 |
| `co2_hall` | rest.scalar.v1 |
| `hydroponic_ph` | rest.chemistry.v1 |
| `water_tank_level` | rest.level.v1 |
| `corridor_pressure` | rest.scalar.v1 |
| `air_quality_pm25` | rest.particulate.v1 |
| `air_quality_voc` | rest.chemistry.v1 |

### Telemetry Streams (SSE/WebSocket)

| Topic | Schema |
|---|---|
| `mars/telemetry/solar_array` | topic.power.v1 |
| `mars/telemetry/radiation` | topic.environment.v1 |
| `mars/telemetry/life_support` | topic.environment.v1 |
| `mars/telemetry/thermal_loop` | topic.thermal_loop.v1 |
| `mars/telemetry/power_bus` | topic.power.v1 |
| `mars/telemetry/power_consumption` | topic.power.v1 |
| `mars/telemetry/airlock` | topic.airlock.v1 |

### Actuators

| Actuator ID | Description |
|---|---|
| `cooling_fan` | Habitat cooling fan |
| `entrance_humidifier` | Entrance air humidifier |
| `hall_ventilation` | Hall ventilation system |
| `habitat_heater` | Habitat heater |

---

## Standard Event Schema

All sensor data (whether originating from REST polling or telemetry streams) is normalized into the following unified internal event format before being published to the RabbitMQ `telemetry` exchange:

```json
{
  "timestamp": "2036-03-08T14:23:05.123Z",
  "sensor_id": "greenhouse_temperature",
  "metric": "temperature_c",
  "value": 27.4,
  "unit": "°C",
  "status": "ok"
}
```

### Field definitions

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 string | Time of measurement |
| `sensor_id` | string | Unique device identifier |
| `metric` | string | Name of the measured quantity |
| `value` | number | Measured value |
| `unit` | string | Unit of measurement |
| `status` | string | `ok`, `warning`, `critical`, or `error` |

### Routing keys

| Source | Exchange | Routing key |
|---|---|---|
| REST sensors (sensor_poller) | `telemetry` | `sensors.normalized` |
| Telemetry streams (telemetry_listener) | `telemetry` | `telemetry.normalized` |

---

## Rule Model

Automation rules follow a simple IF–THEN structure:

```
IF <sensor_id>.<metric> <operator> <threshold>
THEN set <actuator_id> to <ON|OFF>
```

### Supported operators

`>`, `>=`, `=`, `<=`, `<`

### Example

```
IF greenhouse_temperature.temperature_c > 28
THEN set cooling_fan to ON
```

### Rule schema (PostgreSQL)

```sql
CREATE TABLE rules (
    id             SERIAL PRIMARY KEY,
    name           TEXT,
    sensor         TEXT,
    attribute      TEXT,
    operator       TEXT,
    threshold      TEXT,
    actuator       TEXT,
    action         TEXT,
    enabled        BOOLEAN DEFAULT true,
    last_triggered TIMESTAMPTZ,
    last_action    TEXT
);
```

### Rule fields

| Field | Description |
|---|---|
| `name` | Human-readable rule name |
| `sensor` | Sensor ID to monitor |
| `attribute` | Metric name to evaluate |
| `operator` | Comparison operator |
| `threshold` | Numeric threshold value |
| `actuator` | Actuator to control |
| `action` | Target state: `ON` or `OFF` |
| `enabled` | Whether the rule is active |
| `last_triggered` | Timestamp of last successful trigger |
| `last_action` | Description of last action performed (e.g. `cooling_fan set ON`) |

### Rule lifecycle

- Rules are evaluated on every incoming sensor event by the automation engine.
- Only rules with `enabled = true` are evaluated.
- When a rule condition is met, the engine publishes an action message to the RabbitMQ `actions` exchange.
- The frontend module consumes the `actions` exchange, updates the actuator state in memory, and broadcasts the update to all connected clients via WebSocket.
- The `last_triggered` timestamp and `last_action` string are updated in the database each time a rule fires.