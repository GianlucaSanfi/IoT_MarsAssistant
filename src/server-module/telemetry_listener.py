#!/usr/bin/env python3
# =============================================================================
# telemetry_listener.py — Listener parallelo dei topic SSE di telemetria
#
# =============================================================================

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
import time
from typing import Callable

import requests

import config
import normalize
from publisher import get_publisher_factory, BasePublisher

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [telemetry] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_stop_event = threading.Event()


def _handle_signal(signum, frame):
    logger.info("Segnale %s ricevuto, shutdown in corso…", signal.Signals(signum).name)
    _stop_event.set()


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


def _iter_sse_events(response: requests.Response):
    """
    Generatore: itera gli eventi SSE da una response in streaming.
    Ogni evento viene restituito come dict (payload JSON già parsato)
    oppure come stringa grezza se non è JSON valido.

    Yields:
        dict | str
    """
    event_lines: list[str] = []

    for raw_line in response.iter_lines(decode_unicode=True):
        if _stop_event.is_set():
            break

        if raw_line is None:
            continue

        line = raw_line.strip()

        if line == "":
            # Fine evento: assembla e parsa
            if not event_lines:
                continue

            # MANTENIAMO SOLO LE RIGHE CHE INIZIANO CON "data:"
            data_parts = [
                l[len("data:"):].lstrip() for l in event_lines if l.startswith("data:")
            ]

            # Se l'evento non conteneva dati (es. solo heartbeat o id), skippa
            if not data_parts:
                event_lines = []
                continue

            data_str = "\n".join(data_parts)

            try:
                yield json.loads(data_str)
            except json.JSONDecodeError:
                yield data_str

            event_lines = []
        else:
            # Ignora righe di commento SSE (iniziano con ':')
            if not line.startswith(":"):
                event_lines.append(line)


# ---------------------------------------------------------------------------
# Worker: thread per singolo topic
# ---------------------------------------------------------------------------


def _topic_worker(topic: str, publisher_factory: Callable[[], BasePublisher]) -> None:
    """
    Thread dedicato a un singolo topic SSE.

    Crea il proprio publisher al primo avvio e ad ogni riconnessione
    (dopo un errore che ha corrotto lo stato della connessione).
    In questo modo ogni thread possiede una connessione RabbitMQ
    completamente indipendente, rispettando il vincolo di
    non-thread-safety di pika.BlockingConnection.

    Si connette allo stream e rimane in ascolto finché _stop_event non viene
    impostato o si verifica un errore, dopodichè tenta la riconnessione.
    """
    stream_url = f"{config.API_BASE_URL}/api/telemetry/stream/{topic}"
    log = logging.getLogger(f"telemetry.{topic}")

    publisher: BasePublisher | None = None

    try:
        while not _stop_event.is_set():

            # Crea (o ricrea) il publisher all'inizio di ogni ciclo di
            # connessione SSE. In caso di errore il publisher precedente
            # viene chiuso prima di aprirne uno nuovo.
            if publisher is not None:
                try:
                    publisher.close()
                except Exception:
                    pass
                publisher = None

            try:
                publisher = publisher_factory()
            except Exception as exc:
                log.error(
                    "Impossibile creare publisher per il topic '%s': %s — "
                    "nuovo tentativo tra %ss…",
                    topic, exc, config.TELEMETRY_RECONNECT_DELAY_SEC,
                )
                _stop_event.wait(timeout=config.TELEMETRY_RECONNECT_DELAY_SEC)
                continue

            log.info("Connessione al topic '%s'…", topic)
            try:
                with requests.get(
                    stream_url,
                    stream=True,
                    timeout=(
                        config.SENSOR_POLL_TIMEOUT_SEC,
                        config.TELEMETRY_STREAM_TIMEOUT_SEC,
                    ),
                ) as resp:
                    resp.raise_for_status()
                    log.info("Connesso. In ascolto…")

                    for event in _iter_sse_events(resp):
                        if _stop_event.is_set():
                            break

                        if not isinstance(event, dict):
                            log.debug("Evento non-JSON ignorato: %s", event)
                            continue

                        log.debug("Evento ricevuto: %s", event)

                        # Normalizza e pubblica
                        records = normalize.normalize_telemetry([event])
                        publisher.publish_batch(records)
                        log.info(
                            "Pubblicati %d record dal topic '%s'.", len(records), topic
                        )

            except requests.exceptions.HTTPError as exc:
                log.error("HTTP error sul topic '%s': %s", topic, exc)
            except requests.exceptions.ConnectionError as exc:
                log.warning("Connessione persa sul topic '%s': %s", topic, exc)
            except requests.exceptions.Timeout:
                log.warning("Timeout sullo stream del topic '%s'.", topic)
            except Exception as exc:
                log.error("Errore inatteso sul topic '%s': %s", topic, exc)

            if not _stop_event.is_set():
                log.info(
                    "Riconnessione al topic '%s' tra %ss…",
                    topic,
                    config.TELEMETRY_RECONNECT_DELAY_SEC,
                )
                _stop_event.wait(timeout=config.TELEMETRY_RECONNECT_DELAY_SEC)

    finally:
        # Chiusura garantita del publisher del thread anche in caso di
        # eccezioni non gestite o shutdown.
        if publisher is not None:
            try:
                publisher.close()
            except Exception as exc:
                log.warning("Errore chiusura publisher del topic '%s': %s", topic, exc)

    log.info("Thread '%s' terminato.", topic)


# ---------------------------------------------------------------------------
# Fetch topic list
# ---------------------------------------------------------------------------


def _fetch_topic_list() -> list[str]:
    url = f"{config.API_BASE_URL}/api/telemetry/topics"
    resp = requests.get(url, timeout=config.SENSOR_POLL_TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json().get("topics", [])


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run(publisher_factory: Callable[[], BasePublisher]) -> None:
    logger.info(
        "Telemetry listener avviato — publisher factory: %s",
        publisher_factory,
    )

    try:
        topics = _fetch_topic_list()
    except requests.RequestException as exc:
        logger.error("Impossibile recuperare lista topic: %s", exc)
        return

    if not topics:
        logger.warning("Nessun topic disponibile. Uscita.")
        return

    logger.info("Topic disponibili: %s", topics)

    # Avvia un thread per ogni topic.
    # Ogni thread riceve la factory e crea autonomamente il proprio publisher.
    threads: list[threading.Thread] = []
    for topic in topics:
        t = threading.Thread(
            target=_topic_worker,
            args=(topic, publisher_factory),
            name=f"sse-{topic}",
            daemon=True,
        )
        t.start()
        threads.append(t)
        logger.info("Thread avviato per il topic '%s'.", topic)

    # Attende che tutti i thread terminino (o che arrivi lo stop)
    try:
        while not _stop_event.is_set():
            alive = [t for t in threads if t.is_alive()]
            if not alive:
                logger.info("Tutti i thread terminati.")
                break
            time.sleep(1)
    finally:
        _stop_event.set()
        for t in threads:
            t.join(timeout=5)
        logger.info("Telemetry listener fermato.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Telemetry listener — sottoscrizione parallela a topic SSE"
    )
    parser.add_argument(
        "--publisher",
        choices=["print", "rabbitmq"],
        default=config.PUBLISHER_TYPE,
        help=f"Tipo di publisher (default: {config.PUBLISHER_TYPE})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    factory = get_publisher_factory(
        publisher_type=args.publisher,
        routing_key=config.RABBITMQ_TELEMETRY_ROUTING_KEY,
    )
    run(factory)
    