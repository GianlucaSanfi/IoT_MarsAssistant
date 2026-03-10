#!/usr/bin/env python3
# =============================================================================
# sensor_poller.py — Polling periodico dei sensori
#
# =============================================================================

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

import requests

import config
import normalize
from publisher import get_publisher, BasePublisher

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [sensor_poller] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_running = True

def _handle_signal(signum, frame):
    global _running
    logger.info("Segnale %s ricevuto, shutdown in corso…", signal.Signals(signum).name)
    _running = False

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ---------------------------------------------------------------------------
# Core: singolo ciclo di polling
# ---------------------------------------------------------------------------

def _fetch_sensor_list() -> list[str]:
    """Recupera la lista degli ID sensori dall'API."""
    url = f"{config.API_BASE_URL}/api/sensors"
    resp = requests.get(url, timeout=config.SENSOR_POLL_TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json().get("sensors", [])


def _fetch_sensor_data(sensor_id: str) -> dict:
    """Recupera i dati grezzi di un singolo sensore."""
    url = f"{config.API_BASE_URL}/api/sensors/{sensor_id}"
    resp = requests.get(url, timeout=config.SENSOR_POLL_TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()


def poll_once(publisher: BasePublisher) -> int:
    """
    Esegue un singolo ciclo di polling su tutti i sensori.

    Returns:
        Numero di record normalizzati pubblicati.
    """
    try:
        sensor_ids = _fetch_sensor_list()
    except requests.RequestException as exc:
        logger.error("Impossibile recuperare lista sensori: %s", exc)
        return 0

    logger.info("Sensori disponibili: %s", sensor_ids)

    raw_responses: list[dict] = []
    for sid in sensor_ids:
        try:
            data = _fetch_sensor_data(sid)
            raw_responses.append(data)
            logger.debug("Dati ricevuti per '%s': %s", sid, data)
        except requests.RequestException as exc:
            logger.warning("Errore fetch sensore '%s': %s", sid, exc)

    if not raw_responses:
        logger.warning("Nessuna risposta valida in questo ciclo.")
        return 0

    records = normalize.normalize_sensor_responses(raw_responses)
    publisher.publish_batch(records)

    logger.info("Pubblicati %d record da %d sensori.", len(records), len(raw_responses))
    return len(records)


# ---------------------------------------------------------------------------
# Loop principale
# ---------------------------------------------------------------------------

def run(interval_sec: float, publisher: BasePublisher) -> None:
    logger.info(
        "Sensor poller avviato — intervallo: %ss  publisher: %s",
        interval_sec, type(publisher).__name__,
    )
    try:
        while _running:
            poll_once(publisher)
            # Attesa interrompibile: controlla _running ogni secondo
            elapsed = 0.0
            while _running and elapsed < interval_sec:
                time.sleep(1)
                elapsed += 1
    finally:
        publisher.close()
        logger.info("Sensor poller fermato.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sensor poller — polling periodico dei sensori REST")
    parser.add_argument(
        "--interval",
        type=float,
        default=config.SENSOR_POLL_INTERVAL_SEC,
        metavar="SECONDI",
        help=f"Intervallo di polling in secondi (default: {config.SENSOR_POLL_INTERVAL_SEC})",
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
    pub  = get_publisher(
        publisher_type=args.publisher,
        routing_key=config.RABBITMQ_SENSOR_ROUTING_KEY,
    )
    sys.exit(0 if run(args.interval, pub) is None else 1)
