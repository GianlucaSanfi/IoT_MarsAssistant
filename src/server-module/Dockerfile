# =============================================================================
# Dockerfile — Ingestion services (sensor_poller + telemetry_listener)
#
# Immagine unica: il CMD viene sovrascritto dal docker-compose per avviare
# il processo corretto (sensor_poller o telemetry_listener).
# =============================================================================

FROM python:3.12-slim

# Non scrivere .pyc, log non bufferizzati (essenziale per docker logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installa dipendenze prima del codice (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il sorgente
# COPY config.py normalize.py publisher.py sensor_poller.py telemetry_listener.py ./
COPY . . 

# Default: sensor poller — sovrascritto da docker-compose per telemetry_listener
CMD ["python", "sensor_poller.py"]
