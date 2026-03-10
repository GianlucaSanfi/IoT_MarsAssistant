# =============================================================================
# publisher.py — Astrazione dello strato di pubblicazione
#
# Utilizzo:
#   publisher = get_publisher()
#   publisher.publish(record)          # singolo record
#   publisher.publish_batch(records)   # lista di record
# =============================================================================

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interfaccia base
# ---------------------------------------------------------------------------

class BasePublisher(ABC):
    """Interfaccia comune per tutti i publisher."""

    @abstractmethod
    def publish(self, record: dict) -> None:
        """Pubblica un singolo record normalizzato."""

    def publish_batch(self, records: list[dict]) -> None:
        """Pubblica una lista di record. Default: chiama publish() su ognuno."""
        for record in records:
            self.publish(record)

    def close(self) -> None:
        """Rilascia risorse (connessioni, canali, ecc.)."""


# ---------------------------------------------------------------------------
# Publisher: stampa su stdout
# ---------------------------------------------------------------------------

class PrintPublisher(BasePublisher):
    """
    Stampa ogni record come riga JSON compatta su stdout.
    Utile per sviluppo, debug e pipe verso altri processi.
    """

    def publish(self, record: dict) -> None:
        print(json.dumps(record, ensure_ascii=False), flush=True)

    def publish_batch(self, records: list[dict]) -> None:
        for record in records:
            self.publish(record)


# ---------------------------------------------------------------------------
# Publisher: RabbitMQ
# ---------------------------------------------------------------------------

class RabbitMQPublisher(BasePublisher):
    """
    Pubblica record normalizzati su RabbitMQ via pika.

    Configurazione: config.py / variabili d'ambiente (RABBITMQ_*)

    Ogni record viene serializzato come JSON e inviato all'exchange configurato.
    Il routing_key distingue sensori da telemetria:
        sensors.normalized
        telemetry.normalized
        
    """

    def __init__(self, routing_key: str = config.RABBITMQ_SENSOR_ROUTING_KEY):
        self._routing_key = routing_key
        self._connection  = None
        self._channel     = None
        self._connect_with_retry()

    # ------------------------------------------------------------------
    # Connessione
    # ------------------------------------------------------------------

    def _connect_with_retry(self) -> None:
        """
        Tenta la connessione con retry lineare.
        Indispensabile in Docker dove RabbitMQ può impiegare qualche secondo
        in più rispetto al semplice healthcheck TCP.
        """
        max_retries = config.RABBITMQ_STARTUP_MAX_RETRIES
        delay       = config.RABBITMQ_STARTUP_RETRY_DELAY_SEC

        for attempt in range(1, max_retries + 1):
            try:
                self._connect()
                return
            except Exception as exc:
                if attempt == max_retries:
                    logger.error(
                        "RabbitMQ non raggiungibile dopo %d tentativi. Uscita.",
                        max_retries,
                    )
                    raise
                logger.warning(
                    "Connessione a RabbitMQ fallita (tentativo %d/%d): %s "
                    "— nuovo tentativo tra %.0fs…",
                    attempt, max_retries, exc, delay,
                )
                time.sleep(delay)

    def _connect(self) -> None:
        import pika  # type: ignore

        credentials = pika.PlainCredentials(
            config.RABBITMQ_USER,
            config.RABBITMQ_PASSWORD,
        )
        parameters = pika.ConnectionParameters(
            host=config.RABBITMQ_HOST,
            port=config.RABBITMQ_PORT,
            virtual_host=config.RABBITMQ_VHOST,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=30,
        )
        self._connection = pika.BlockingConnection(parameters)
        self._channel    = self._connection.channel()

        # Exchange di tipo "topic": routing flessibile tramite pattern
        self._channel.exchange_declare(
            exchange=config.RABBITMQ_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        
        # 1. Coda 'sensors'
        self._channel.queue_declare(queue="sensors", durable=True)
        self._channel.queue_bind(
            exchange=config.RABBITMQ_EXCHANGE,
            queue="sensors",
            routing_key=config.RABBITMQ_SENSOR_ROUTING_KEY
        )

        # 2. Coda 'telemetry'
        self._channel.queue_declare(queue="telemetry", durable=True)
        self._channel.queue_bind(
            exchange=config.RABBITMQ_EXCHANGE,
            queue="telemetry",
            routing_key=config.RABBITMQ_TELEMETRY_ROUTING_KEY
        )
        
        logger.info(
            "RabbitMQ connesso → %s:%s  vhost=%s  exchange=%s  routing_key=%s",
            config.RABBITMQ_HOST, config.RABBITMQ_PORT, config.RABBITMQ_VHOST,
            config.RABBITMQ_EXCHANGE, self._routing_key,
        )

    # ------------------------------------------------------------------
    # Pubblicazione
    # ------------------------------------------------------------------

    def publish(self, record: dict) -> None:
        import pika  # type: ignore

        body = json.dumps(record, ensure_ascii=False).encode("utf-8")
        props = pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
        )

        try:
            self._channel.basic_publish(
                exchange=config.RABBITMQ_EXCHANGE,
                routing_key=self._routing_key,
                body=body,
                properties=props,
            )
        except Exception as exc:
            logger.warning("Errore publish, tentativo riconnessione: %s", exc)
            self._connect_with_retry()
            self._channel.basic_publish(
                exchange=config.RABBITMQ_EXCHANGE,
                routing_key=self._routing_key,
                body=body,
                properties=props,
            )

    # ------------------------------------------------------------------
    # Chiusura
    # ------------------------------------------------------------------

    def close(self) -> None:
        try:
            if self._connection and not self._connection.is_closed:
                self._connection.close()
                logger.info("Connessione RabbitMQ chiusa.")
        except Exception as exc:
            logger.warning("Errore chiusura RabbitMQ: %s", exc)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_publisher(
    publisher_type: str | None = None,
    routing_key: str = config.RABBITMQ_SENSOR_ROUTING_KEY,
) -> BasePublisher:
    """
    Restituisce il publisher configurato.

    Args:
        publisher_type: "print" | "rabbitmq"  (default: letto da config.PUBLISHER_TYPE)
        routing_key:    routing key RabbitMQ
    """
    ptype = (publisher_type or config.PUBLISHER_TYPE).lower()

    if ptype == "rabbitmq":
        return RabbitMQPublisher(routing_key=routing_key)
    if ptype == "print":
        return PrintPublisher()

    raise ValueError(f"Publisher non supportato: '{ptype}'. Valori validi: 'print', 'rabbitmq'.")

def get_publisher_factory(
    publisher_type: str | None = None,
    routing_key: str = config.RABBITMQ_SENSOR_ROUTING_KEY,
):
    """
    Restituisce una callable (factory) che crea un publisher indipendente
    ogni volta che viene invocata.

    """
    ptype = (publisher_type or config.PUBLISHER_TYPE).lower()

    if ptype not in ("rabbitmq", "print"):
        raise ValueError(f"Publisher non supportato: '{ptype}'. Valori validi: 'print', 'rabbitmq'.")

    def factory() -> BasePublisher:
        return get_publisher(publisher_type=ptype, routing_key=routing_key)

    return factory
