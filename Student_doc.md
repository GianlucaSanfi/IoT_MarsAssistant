# SYSTEM DESCRIPTION:

MARS ASSISTANT is a distributed, event-driven IoT platform designed to monitor and automate the environmental control of a Mars habitat. The system ingests real-time data from 15 environmental sensors (8 REST-polled and 7 telemetry streams), evaluates automation rules, controls 4 physical actuators, and presents a live web-based dashboard to the mission crew.

The platform is composed of five Docker containers communicating over a private network:

- **ingestion_services**: Python-based data ingestion layer (sensor_poller + telemetry_listener)
- **rabbitmq**: Message broker providing decoupled, event-driven communication via topic exchanges
- **automation-engine**: Node.js rule evaluation engine that subscribes to sensor events and triggers actuator commands
- **frontend-module**: Node.js/Express backend gateway that bridges RabbitMQ to the browser via WebSocket and exposes the REST API
- **postgres**: PostgreSQL database for persistent storage of automation rules

All inter-service communication passes through RabbitMQ. The only direct HTTP call is from the frontend-module to the simulator's actuator REST API. The sensor cache is maintained in-memory in the frontend-module and rebuilt automatically on restart. The system is fully containerized and started with a single `docker compose up` command.

---

# USER STORIES:

1. As a user, I want to click on a sensor widget to open a dedicated detail view showing the current state, metrics, and recent log, so that I can monitor a specific environmental parameter in depth.  

2. As a user, I want to view all sensors' states in a unified dashboard with live updates, so that I can have a complete overview of the Mars habitat environment at a glance.  

3. As a user, I want to be notified when a sensor status is "warning", so that I can react promptly to dangerous conditions.  

4. As a user, I want to view each actuator's current state (ON/OFF) in a dedicated card widget with real-time updates, last change time, and trigger source, so that I always know the actual state of the system.  

5. As a user, I want to view all actuators' states in a unified dashboard where each device has its own card with live status indicators, so that I can monitor and manage the entire system from a single screen.  

6. As a user, I want to toggle an actuator's state by directly interacting with its widget, so that I can manually intervene on the environment without navigating to a separate settings page.  

7. As a user, I want to see the last time an actuator state changed and what triggered the change (manual command or automation rule), so that I can understand recent interventions on the system.  

8. As a user, I want to receive a visual confirmation when I manually toggle an actuator, so that I know my command was received by the system.  

9. As a user, I want to create an automation rule using a simple if-then interface (e.g., if temperature > 30°C → turn on fan), so that I can automate environmental control without writing code.  

10. As a user, I want to edit an existing automation rule, so that I can adapt the system's behaviour as mission parameters change.  

11. As a user, I want to delete an automation rule, so that I can remove obsolete logic and keep the system clean.  

12. As a user, I want to view a list of all automation rules with their current status (active/disabled), so that I can have a clear picture of what logic is running.  

13. As a user, I want to disable an automation rule without deleting it, so that I can temporarily suspend its behaviour and re-enable it later when needed.  

14. As a user, I want to see when an automation rule was last triggered and what action it performed (e.g., "cooling_fan set ON"), so that I can verify if the rule is behaving as intended.  

15. As a user, I want to see the overall system connection status in the top bar, so that I always know if the platform is live or offline.  

---

# CONTAINERS:

## CONTAINER_NAME: ingestion_services

### DESCRIPTION: 
A Docker container based on Python 3.12-slim that acts as the data ingestion layer of the system. It is designed to run the two core processes: a periodic sensor polling service and a real-time telemetry (SSE) listener. Both processes fetch data from the IoT simulator container, normalize the semi-structured JSON payloads into a flat standard format, and publish the records to RabbitMQ as a server broker.

### USER STORIES:
- US-2: Live sensor dashboard — data is continuously ingested and forwarded
- US-3: Warning notifications — status field is normalized and forwarded
- US-15: System connection status — ingestion feeds the live pipeline

### PORTS: 
None exposed: internal communication only via RabbitMQ (AMQP)

### PERSISTENCE EVALUATION
The container is completely stateless. No data is persisted locally on the container's file system. All fetched, parsed, and normalized data is immediately forwarded to RabbitMQ

### EXTERNAL SERVICES CONNECTIONS
* External REST API: Connects via HTTP/GET to `http://simulator:8080` to fetch available sensors and topics, and retrieves data via standard endpoints and SSE streams
* RabbitMQ: Connects to the AMQP message broker to publish normalized metrics on exchange `telemetry`, routing keys `sensors.normalized` and `telemetry.normalized`

### MICROSERVICES:

#### MICROSERVICE: sensor_poller
- TYPE: backend
- DESCRIPTION: A synchronous worker process that periodically polls a REST API for sensor data. It fetches the list of available sensors, retrieves their current state, normalizes the nested JSON structures into flat records, and publishes them in batches to the server broker.
- PORTS: None
- TECHNOLOGICAL SPECIFICATION: 
Written in Python 3.12. Uses the `requests` library for synchronous HTTP GET requests and `pika` for AMQP communication with RabbitMQ.
- SERVICE ARCHITECTURE: 
Operates on a continuous polling loop with a configurable sleep interval (default 10 seconds, via `SENSOR_POLL_INTERVAL_SEC` env var). In each cycle it queries the simulator for active sensor IDs, fetches data for each ID sequentially, normalizes the responses into a unified event schema, and publishes to RabbitMQ on routing key `sensors.normalized`.

#### MICROSERVICE: telemetry_listener
- TYPE: backend
- DESCRIPTION: An asynchronous worker process that maintains long-lived Server-Sent Events (SSE) connections to stream real-time telemetry data. It listens to multiple topics simultaneously, normalizes incoming events on the fly, and publishes them to the message broker.
- PORTS: None
- TECHNOLOGICAL SPECIFICATION: 
Written in Python 3.12. Uses `requests` with `stream=True` to parse SSE chunks and `pika` for RabbitMQ. Utilizes the built-in `threading` module for concurrency.
- SERVICE ARCHITECTURE: 
Multi-threaded architecture. On startup, fetches the list of available telemetry topics from the simulator API. Spawns a dedicated daemon thread per topic. Each thread handles automatic reconnection with backoff delay in case the SSE stream drops or times out. Publishes to RabbitMQ on routing key `telemetry.normalized`.

---

## CONTAINER_NAME: automation-engine

### DESCRIPTION: 
A Node.js container that implements the automation rule engine. It subscribes to the RabbitMQ `telemetry` exchange, evaluates IF-THEN rules loaded from PostgreSQL against incoming sensor events, and publishes actuator command messages to the RabbitMQ `actions` exchange when a rule condition is satisfied.

### USER STORIES:
- US-9: Create automation rule
- US-10: Edit automation rule
- US-11: Delete automation rule
- US-12: View automation rules list
- US-13: Disable/enable automation rule
- US-14: See last triggered and last action

### PORTS: 
None exposed: communicates only via RabbitMQ and PostgreSQL

### PERSISTENCE EVALUATION
The container is stateless. All rule definitions, enabled flags, and `last_triggered` timestamps are persisted in the PostgreSQL database. The engine loads only enabled rules (`WHERE enabled = true`) and refreshes them every 5 seconds (`RULES_REFRESH_MS`).

### EXTERNAL SERVICES CONNECTIONS
- RabbitMQ: subscribes to `telemetry` exchange (queue: `automation-engine`, routing keys: `sensors.normalized`, `telemetry.normalized`), publishes to `actions` exchange
- PostgreSQL: reads enabled rules, writes `last_triggered` on each rule trigger

### MICROSERVICES:

#### MICROSERVICE: engine
- TYPE: backend
- DESCRIPTION: The core rule evaluation process. Subscribes to the RabbitMQ telemetry exchange, maintains an in-memory cache of enabled rules refreshed from PostgreSQL every 5 seconds, and evaluates each incoming sensor event against all active rules. When a condition is satisfied, publishes an action command to the `actions` exchange and updates `last_triggered` in the DB.
- PORTS: None
- TECHNOLOGICAL SPECIFICATION:
Written in Node.js. Uses `amqplib` for RabbitMQ communication and `pg` (node-postgres) for PostgreSQL access. No HTTP framework — pure event-driven process.
- SERVICE ARCHITECTURE:
On startup, waits 3 seconds for dependencies, then loads rules from DB and starts a periodic refresh every `RULES_REFRESH_MS` (default 5000ms). Connects to RabbitMQ with automatic reconnection (up to 15 retries, 5s delay). Consumes from a durable queue `automation-engine` bound to the `telemetry` exchange on routing keys `sensors.normalized` and `telemetry.normalized`. For each message, evaluates all enabled rules using operators `>`, `<`, `>=`, `<=`, `==`, `!=` against the sensor's metric value. On match, publishes a JSON payload to the `actions` exchange and persists `last_triggered` to PostgreSQL.

- DB STRUCTURE:

  **_rules_** : | **_id_** | name | sensor | attribute | operator | threshold | actuator | action | enabled | last_triggered | last_action |

---


## CONTAINER_NAME: frontend-module

### DESCRIPTION: 
A Node.js + Express container that acts as the backend gateway between RabbitMQ and the browser. It subscribes to the `telemetry`, `actions`, and `alerts` RabbitMQ exchanges, maintains an in-memory sensor cache and actuator state, exposes a REST API for rules and actuator control, runs a WebSocket server to push live updates to connected browsers, and serves the static HTML/CSS/JS dashboard.

### USER STORIES:
- US-1: Sensor detail popup
- US-2: Unified sensor dashboard with live updates
- US-3: Warning notifications via alert glow
- US-4: Actuator state card with real-time updates
- US-5: Unified actuator dashboard
- US-6: Manual actuator toggle
- US-7: Last change time and trigger source
- US-8: Visual confirmation on toggle
- US-9: Create automation rule
- US-10: Edit automation rule
- US-11: Delete automation rule
- US-12: View automation rules list
- US-13: Disable/enable automation rule
- US-14: See last triggered and last action
- US-15: System connection status indicator

### PORTS: 
8000 (HTTP + WebSocket)

### PERSISTENCE EVALUATION
The container is mostly stateless. The sensor cache (`sensorCache`) and actuator state (`actuatorState`) are maintained in-memory and lost on restart — rebuilt automatically within seconds as new data arrives from RabbitMQ. Automation rules are persisted in PostgreSQL.

### EXTERNAL SERVICES CONNECTIONS
- RabbitMQ: subscribes to `telemetry` exchange (queue: `frontend-telemetry`, routing keys: `sensors.normalized`, `telemetry.normalized`), `actions` exchange (routing key: `#`), and `alerts` exchange (fanout)
- PostgreSQL: reads and writes automation rules via the `/api/rules` REST API
- Mars IoT Simulator (`http://simulator:8080`) — forwards actuator commands via POST `/api/actuators/:id`

### MICROSERVICES:

#### MICROSERVICE: server
- TYPE: backend
- DESCRIPTION: Express HTTP server and WebSocket server. Consumes RabbitMQ messages from three exchanges and broadcasts them to connected browsers via WebSocket. Maintains in-memory sensor cache and actuator state. Exposes REST endpoints for rules CRUD and actuator control. On new WebSocket connection, sends the full sensor cache and current actuator states as an initial snapshot.
- PORTS: 8000
- TECHNOLOGICAL SPECIFICATION:
Written in Node.js. Uses `express` for HTTP, `ws` for WebSocket, `amqplib` for RabbitMQ, and `pg` (node-postgres) for PostgreSQL.
- SERVICE ARCHITECTURE:
On startup, binds HTTP and WebSocket server on port 8000 and connects to RabbitMQ with automatic reconnection (up to 15 retries, 5s delay). Subscribes to three exchanges: `telemetry` (durable queue `frontend-telemetry`) for sensor data, `actions` (exclusive queue, routing `#`) for actuator commands from the automation engine, and `alerts` (fanout, exclusive queue) for alert notifications. Incoming telemetry messages update `sensorCache` and are broadcast to all WebSocket clients. Incoming action messages update `actuatorState` and are broadcast as `actuator_update` events. New WebSocket clients receive a full snapshot of `sensorCache` and `actuatorState` on connection.

- ENDPOINTS:

	| HTTP METHOD | URL | Description | User Stories |
	| ----------- | --- | ----------- | ------------ |
	| GET | / | Serve the static dashboard HTML page | US-2, US-5, US-12 |
	| GET | /actuators | Return current in-memory state of all 4 actuators | US-4, US-5 |
	| POST | /actuators/:id | Set actuator state (ON/OFF), update in-memory state | US-6, US-7, US-8 |
	| GET | /api/rules | Return all automation rules from PostgreSQL | US-12 |
	| GET | /api/rules/:id | Return a single automation rule by ID | US-10 |
	| POST | /api/rules | Create a new automation rule | US-9 |
	| PUT | /api/rules/:id | Update an existing automation rule | US-10 |
	| DELETE | /api/rules/:id | Delete an automation rule | US-11 |
	| PATCH | /api/rules/:id/toggle | Toggle enabled flag of a rule (NOT enabled) | US-13 |
	| WS | ws://host:8000 | Push `sensor_data`, `actuator_update`, `alert` events | US-2, US-3, US-4, US-15 |

#### MICROSERVICE: dashboard
- TYPE: frontend
- DESCRIPTION: Single-page HTML/CSS/JS application served as a static file by the Node.js server. Connects to the WebSocket server to receive live sensor and actuator updates. Provides the sensor grid, actuator control panel, and automation rules management interface.
- PORTS: None: served as static file from port 8000
- TECHNOLOGICAL SPECIFICATION:
Vanilla HTML5, CSS3, JavaScript. No frontend framework. Uses the browser-native WebSocket API and `fetch` for REST calls. Fonts: Orbitron, Exo 2, Share Tech Mono (Google Fonts).
- SERVICE ARCHITECTURE:
On load, connects to `ws://host:8000` and receives an initial snapshot of the full sensor cache and actuator states. Incoming WebSocket events (`sensor_data`, `actuator_update`, `alert`) update widgets in real-time. Auto-reconnects with exponential backoff on disconnect. The automation rules table is loaded via REST `GET /api/rules`. Rule CRUD and actuator toggles are sent via REST to the server backend.

- PAGES:

	| Name | Description | Related Microservice | User Stories |
	| ---- | ----------- | -------------------- | ------------ |
	| Sensors | Live grid of 15 sensor widgets (8 REST + 7 telemetry streams) with sparklines, multi-metric display, and alert glow on warning status. Click on a widget opens a detail popup with live charts and recent data log. | server (WebSocket) | US-1, US-2, US-3, US-15 |
	| Actuators | Grid of 4 actuator cards with ON/OFF toggle, last change timestamp, and trigger source (manual or rule). Visual flash confirmation on toggle. | server (REST + WebSocket) | US-4, US-5, US-6, US-7, US-8 |
	| Automations | Table of all automation rules with enabled/disabled status pill, last triggered timestamp, last action string. Modal form for create/edit. Enable/disable toggle and delete per rule. | server (REST) | US-9, US-10, US-11, US-12, US-13, US-14 |

---

## CONTAINER_NAME: postgres

### DESCRIPTION: 
Standard PostgreSQL 15 container used as the persistent storage layer for automation rules. Initialized on first start with `init.sql` which creates the `rules` table schema.

### USER STORIES:
- US-9: Create rule - persisted to DB
- US-10: Edit rule - updated in DB
- US-11: Delete rule - removed from DB
- US-12: View rules — read from DB
- US-13: Disable rule — `enabled` flag updated in DB
- US-14: Last triggered / last action — `last_triggered` and `last_action` written on each rule trigger

### PORTS: 
5432

### PERSISTENCE EVALUATION
Full persistence via Docker volume `postgres_data` mounted at `/var/lib/postgresql/data`. All automation rules, their enabled state, `last_triggered` timestamps, and `last_action` strings survive container restarts.

### EXTERNAL SERVICES CONNECTIONS
None. Accessed only by `automation-engine` and `frontend-module` on the internal `iot-net` network.

### MICROSERVICES:

#### MICROSERVICE: postgres
- TYPE: backend
- DESCRIPTION: Standard PostgreSQL 15 database engine. No custom application code — schema is initialized via `init.sql` mounted at `/docker-entrypoint-initdb.d/init.sql` on first container start.
- PORTS: 5432
- TECHNOLOGICAL SPECIFICATION:
PostgreSQL 15 official Docker image. Database: `iotdb`, user: `iot`. Schema initialized automatically from `init.sql` on first boot.
- SERVICE ARCHITECTURE:
Standard relational database. Accessed by two services: `automation-engine` (reads enabled rules, writes `last_triggered`) and `frontend-module` (full rules CRUD via REST API). No custom logic runs inside the container.

- DB STRUCTURE:

  **_rules_** : | **_id_** | name | sensor | attribute | operator | threshold | actuator | action | enabled | last_triggered | last_action |