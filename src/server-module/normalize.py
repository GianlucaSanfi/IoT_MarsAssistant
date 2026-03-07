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

    Strategie (in ordine):
        1. Campi diretti metric/value/unit  → 1 record
        2. Lista 'measurements'             → N record (uno per metrica)
        3. Campi piatti via SENSOR_FLAT_FIELD_MAP → N record
        4. Fallback                         → 1 record con valori None
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
    Normalizza una lista di payload SSE già deserializzati (dict) in record
    piatti e uniformi.

    Nota: accetta direttamente la lista di dict prodotta dal listener SSE
    (non la stringa SSE grezza — quella viene parsata dal listener stesso).

    Schema output per ogni record:
        timestamp  — ISO 8601 string (UTC)
        sensor_id  — ultimo segmento del topic (es. "solar_array")
        metric     — nome della metrica
        value      — valore della metrica
        unit       — unità di misura (None se non applicabile)
        status     — "ok" | "warning" | "unknown"

    Strategie (in ordine):
        1. Lista 'measurements'                    → N record
        2. Campi piatti via TELEMETRY_FLAT_FIELD_MAP → N record
        3. Fallback                                → 1 record con valori None
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


# ---------------------------------------------------------------------------
# Demo / test rapido
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_sensors = [
        {"sensor_id": "greenhouse_temperature", "captured_at": "2026-03-07T11:40:36+00:00",
         "metric": "temperature_c", "value": 23.71, "unit": "C", "status": "ok"},
        {"sensor_id": "hydroponic_ph", "captured_at": "2026-03-07T11:40:36+00:00",
         "measurements": [{"metric": "ph", "value": 6.38, "unit": "pH"}], "status": "ok"},
        {"sensor_id": "water_tank_level", "captured_at": "2026-03-07T11:40:36+00:00",
         "level_pct": 69.36, "level_liters": 2774.4, "status": "ok"},
    ]
    print("=== SENSORI ===")
    print(json.dumps(normalize_sensor_responses(sample_sensors), indent=2))

    sample_telemetry = [
        {"topic": "facility/solar_array", "event_time": "2026-03-07T12:00:00+00:00",
         "power_kw": 42.5, "voltage_v": 380.0, "current_a": 111.8,
         "cumulative_kwh": 1500.0, "status": "ok"},
        {"topic": "facility/thermal_loop", "event_time": "2026-03-07T12:00:01+00:00",
         "measurements": [
             {"metric": "temperature_c", "value": 35.2, "unit": "°C"},
             {"metric": "flow_l_min",    "value": 12.4,  "unit": "L/min"},
         ], "status": "ok"},
    ]
    print("\n=== TELEMETRIA ===")
    print(json.dumps(normalize_telemetry(sample_telemetry), indent=2))
