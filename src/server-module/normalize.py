# =============================================================================
# normalize.py — Normalizzazione record sensori e telemetria SSE
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime


# ---------------------------------------------------------------------------
# FLAT_FIELD_MAP — sensori con struttura a campi piatti non standard
# ---------------------------------------------------------------------------

SENSOR_FLAT_FIELD_MAP: dict[str, list[dict]] = {
    "water_tank_level": [
        {"field": "level_pct",    "metric": "level_pct",    "unit": "%"},
        {"field": "level_liters", "metric": "level_liters", "unit": "L"},
    ],
    "air_quality_pm25": [
        {"field": "pm1_ug_m3",  "metric": "pm1_ug_m3",  "unit": "µg/m³"},
        {"field": "pm25_ug_m3", "metric": "pm25_ug_m3", "unit": "µg/m³"},
        {"field": "pm10_ug_m3", "metric": "pm10_ug_m3", "unit": "µg/m³"},
    ],
}

TELEMETRY_FLAT_FIELD_MAP: dict[str, list[dict]] = {
    "solar_array": [
        {"field": "power_kw",       "metric": "power_kw",       "unit": "kW"},
        {"field": "voltage_v",      "metric": "voltage_v",      "unit": "V"},
        {"field": "current_a",      "metric": "current_a",      "unit": "A"},
        {"field": "cumulative_kwh", "metric": "cumulative_kwh", "unit": "kWh"},
    ],
    "thermal_loop": [
        {"field": "temperature_c",  "metric": "temperature_c",  "unit": "°C"},
        {"field": "flow_l_min",     "metric": "flow_l_min",     "unit": "L/min"},
    ],
    "power_bus": [
        {"field": "power_kw",       "metric": "power_kw",       "unit": "kW"},
        {"field": "voltage_v",      "metric": "voltage_v",      "unit": "V"},
        {"field": "current_a",      "metric": "current_a",      "unit": "A"},
        {"field": "cumulative_kwh", "metric": "cumulative_kwh", "unit": "kWh"},
    ],
    "power_consumption": [
        {"field": "power_kw",       "metric": "power_kw",       "unit": "kW"},
        {"field": "voltage_v",      "metric": "voltage_v",      "unit": "V"},
        {"field": "current_a",      "metric": "current_a",      "unit": "A"},
        {"field": "cumulative_kwh", "metric": "cumulative_kwh", "unit": "kWh"},
    ],
    "airlock": [
        {"field": "cycles_per_hour", "metric": "cycles_per_hour", "unit": "cycles/h"},
        {"field": "last_state",      "metric": "last_state",      "unit": None},
    ],
}


# ---------------------------------------------------------------------------
# Normalizzazione SENSORI
# ---------------------------------------------------------------------------

def normalize_sensor_responses(raw_responses: list[dict]) -> list[dict]:
    """
    Normalizza una lista di raw response di sensori in record piatti e uniformi.

    Schema output per ogni record:
        timestamp  — ISO 8601 string (UTC)
        sensor_id  — identificatore del sensore
        metric     — nome della metrica
        value      — valore numerico
        unit       — unità di misura
        status     — "ok" | "warning" | "unknown"
    """
    normalized: list[dict] = []

    for raw in raw_responses:
        sensor_id  = raw.get("sensor_id")
        timestamp  = _parse_timestamp(raw.get("captured_at"))
        status     = raw.get("status", "unknown")

        def make_row(metric, value, unit) -> dict:
            return {
                "timestamp": timestamp,
                "sensor_id": sensor_id,
                "metric":    metric,
                "value":     value,
                "unit":      unit,
                "status":    status,
            }

        if "metric" in raw and "value" in raw:
            normalized.append(make_row(raw["metric"], raw["value"], raw.get("unit")))

        elif "measurements" in raw:
            for m in raw["measurements"]:
                normalized.append(make_row(m.get("metric"), m.get("value"), m.get("unit")))

        elif sensor_id in SENSOR_FLAT_FIELD_MAP:
            for mapping in SENSOR_FLAT_FIELD_MAP[sensor_id]:
                field = mapping["field"]
                if field in raw:
                    normalized.append(make_row(mapping["metric"], raw[field], mapping["unit"]))

        else:
            normalized.append(make_row(None, None, None))

    return normalized


# ---------------------------------------------------------------------------
# Normalizzazione TELEMETRIA SSE
# ---------------------------------------------------------------------------

def normalize_telemetry(raw_events: list[dict]) -> list[dict]:
    """
    Normalizza una lista di payload SSE in record piatti e uniformi.

    Schema output per ogni record:
        timestamp  — ISO 8601 string (UTC)
        sensor_id  — ultimo segmento del topic (es. "solar_array")
        metric     — nome della metrica
        value      — valore della metrica
        unit       — unità di misura (None se non applicabile)
        status     — "ok" | "warning" | "unknown"

    """
    normalized: list[dict] = []

    for event in raw_events:
        topic     = event.get("topic", "")
        sensor_id = topic.split("/")[-1] if topic else event.get("sensor_id", "unknown")
        timestamp = _parse_timestamp(event.get("event_time") or event.get("timestamp"))
        status    = event.get("status", "unknown")

        def make_row(metric, value, unit) -> dict:
            return {
                "timestamp": timestamp,
                "sensor_id": sensor_id,
                "metric":    metric,
                "value":     value,
                "unit":      unit,
                "status":    status,
            }

        if "measurements" in event:
            for m in event["measurements"]:
                normalized.append(make_row(m.get("metric"), m.get("value"), m.get("unit")))

        elif sensor_id in TELEMETRY_FLAT_FIELD_MAP:
            for mapping in TELEMETRY_FLAT_FIELD_MAP[sensor_id]:
                field = mapping["field"]
                if field in event:
                    normalized.append(make_row(mapping["metric"], event[field], mapping["unit"]))

        else:
            normalized.append(make_row(None, None, None))

    return normalized


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_timestamp(raw_ts: str | None) -> str | None:
    """Restituisce il timestamp come stringa ISO 8601; None se non parsabile."""
    if not raw_ts:
        return None
    try:
        return datetime.fromisoformat(raw_ts).isoformat()
    except (ValueError, TypeError):
        return raw_ts
