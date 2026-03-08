# MARS ASSISTANT
Containerized application for collecting heterogeneous IoT sensor data, live monitoring and automation of Mars habitat environment using simple IF-THEN rules to control actuators.

## Run

```bash
cd src
docker compose up -d
```

Open [http://localhost:8000](http://localhost:8000)

## Stop

```bash
docker compose down
```
### NOTE:  
to delete the database rules (volumes)
```bash
docker compose down -v
```

## Rebuild (after code changes)

```bash
docker compose up --build -d
```