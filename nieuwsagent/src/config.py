"""
config.py — Laadt de NieuwsAgent-configuratie.

Productie (Home Assistant): leest uit /data/options.json
Lokaal testen: valt terug op omgevingsvariabelen en standaardwaarden.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_HA_OPTIONS_PATH = Path("/data/options.json")


def load_config() -> dict:
    """
    Laad de configuratie en geef een dict terug.

    Volgorde:
    1. /data/options.json  (Home Assistant productie)
    2. Omgevingsvariabelen met standaardwaarden (lokaal testen)
    """
    if _HA_OPTIONS_PATH.exists():
        return _load_from_ha()
    return _load_from_env()


def _load_from_ha() -> dict:
    """Laad configuratie uit Home Assistant's options.json."""
    try:
        raw = _HA_OPTIONS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        config = _apply_defaults(data)
        logger.info(
            "Configuratie geladen vanuit %s (Home Assistant modus)", _HA_OPTIONS_PATH
        )
        return config
    except json.JSONDecodeError as exc:
        logger.error(
            "Kon %s niet parsen als JSON: %s — valt terug op omgevingsvariabelen",
            _HA_OPTIONS_PATH,
            exc,
        )
        return _load_from_env()
    except OSError as exc:
        logger.error(
            "Kon %s niet lezen: %s — valt terug op omgevingsvariabelen",
            _HA_OPTIONS_PATH,
            exc,
        )
        return _load_from_env()


def _load_from_env() -> dict:
    """Laad configuratie uit omgevingsvariabelen (lokaal testen)."""
    config = _apply_defaults(
        {
            "gmail_address": os.getenv("GMAIL_ADDRESS", ""),
            "gmail_app_password": os.getenv("GMAIL_APP_PASSWORD", ""),
            "ontvanger_email": os.getenv("ONTVANGER_EMAIL", ""),
            "ollama_url": os.getenv("OLLAMA_URL", ""),
            "ollama_model": os.getenv("OLLAMA_MODEL", ""),
            "tijdstip_ochtend": os.getenv("TIJDSTIP_OCHTEND", ""),
            "tijdstip_avond": os.getenv("TIJDSTIP_AVOND", ""),
        }
    )
    logger.info("Configuratie geladen vanuit omgevingsvariabelen (lokale modus)")
    return config


def _apply_defaults(data: dict) -> dict:
    """Vul ontbrekende of lege velden aan met standaardwaarden."""
    defaults: dict = {
        "gmail_address": "",
        "gmail_app_password": "",
        "ontvanger_email": "",
        "ollama_url": "http://homeassistant:11434",
        "ollama_model": "qwen2.5:3b",
        "tijdstip_ochtend": "06:00",
        "tijdstip_avond": "17:00",
    }

    result = dict(defaults)
    for key, value in data.items():
        # Overschrijf alleen als de waarde niet leeg is
        if value not in (None, ""):
            result[key] = value

    return result
