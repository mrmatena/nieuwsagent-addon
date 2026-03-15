"""
config.py — Laadt de NieuwsAgent-configuratie.

Volgorde:
1. config.json in de projectroot (standalone gebruik)
2. Omgevingsvariabelen met standaardwaarden (lokaal testen)
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    """
    Laad de configuratie en geef een dict terug.

    Volgorde:
    1. config.json naast de projectroot  (standalone Mac gebruik)
    2. Omgevingsvariabelen               (lokaal testen via terminal)
    """
    if _CONFIG_PATH.exists():
        return _load_from_json()
    return _load_from_env()


def _load_from_json() -> dict:
    """Laad configuratie uit config.json."""
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        config = _apply_defaults(data)
        logger.info("Configuratie geladen vanuit %s", _CONFIG_PATH)
        return config
    except json.JSONDecodeError as exc:
        logger.error(
            "Kon %s niet parsen als JSON: %s — valt terug op omgevingsvariabelen",
            _CONFIG_PATH,
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
        "ollama_url": "http://localhost:11434",
        "ollama_model": "qwen2.5:14b",
    }

    result = dict(defaults)
    for key, value in data.items():
        if value not in (None, ""):
            result[key] = value

    return result
