# =============================================================================
# config.py — Configurazione centralizzata del sistema di ingestion
#
# In Docker tutte le costanti vengono lette da variabili d'ambiente.
# I valori hardcoded sono i default per sviluppo locale.
# =============================================================================

import os

def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)

def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))

def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


# --- API ---
API_BASE_URL = _env_str("API_BASE_URL", "http://host.docker.internal:8080")

# --- Sensor Poller ---
SENSOR_POLL_INTERVAL_SEC = _env_float("SENSOR_POLL_INTERVAL_SEC", 10)
SENSOR_POLL_TIMEOUT_SEC  = _env_float("SENSOR_POLL_TIMEOUT_SEC",   5)

# --- Telemetry Listener ---
TELEMETRY_RECONNECT_DELAY_SEC = _env_float("TELEMETRY_RECONNECT_DELAY_SEC",  5)
TELEMETRY_STREAM_TIMEOUT_SEC  = _env_float("TELEMETRY_STREAM_TIMEOUT_SEC",  30)

# --- Publisher ---
# "print" | "rabbitmq"
PUBLISHER_TYPE = _env_str("PUBLISHER_TYPE", "print")

# --- RabbitMQ (usato solo se PUBLISHER_TYPE == "rabbitmq") ---
RABBITMQ_HOST     = _env_str("RABBITMQ_HOST",     "rabbitmq")
RABBITMQ_PORT     = _env_int("RABBITMQ_PORT",      5672)
RABBITMQ_VHOST    = _env_str("RABBITMQ_VHOST",    "/")
RABBITMQ_USER     = _env_str("RABBITMQ_USER",     "guest")
RABBITMQ_PASSWORD = _env_str("RABBITMQ_PASSWORD", "guest")
RABBITMQ_EXCHANGE = _env_str("RABBITMQ_EXCHANGE", "telemetry")

RABBITMQ_SENSOR_ROUTING_KEY    = _env_str("RABBITMQ_SENSOR_ROUTING_KEY",    "sensors.normalized")
RABBITMQ_TELEMETRY_ROUTING_KEY = _env_str("RABBITMQ_TELEMETRY_ROUTING_KEY", "telemetry.normalized")

# Retry all'avvio mentre RabbitMQ si sta ancora inizializzando
RABBITMQ_STARTUP_RETRY_DELAY_SEC = _env_float("RABBITMQ_STARTUP_RETRY_DELAY_SEC", 3)
RABBITMQ_STARTUP_MAX_RETRIES     = _env_int("RABBITMQ_STARTUP_MAX_RETRIES",       20)
