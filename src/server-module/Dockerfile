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

WORKDIR /server-module

# Installa dipendenze prima del codice (layer cache)
COPY server-module/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il sorgente
COPY server-module/config.py server-module/normalize.py server-module/publisher.py server-module/sensor_poller.py server-module/telemetry_listener.py ./server-module/

# Default: sensor poller — sovrascritto da docker-compose per telemetry_listener
CMD ["python", "sensor_poller.py"]
