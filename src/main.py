"""
main.py — NieuwsAgent hoofdscript (run-once).

Gebruik:
    python3 src/main.py Ochtend
    python3 src/main.py Avond

Wordt aangeroepen door launchd op 07:00 en 17:00.
"""

import sys
import logging
import datetime
from pathlib import Path

# Voeg src/ toe aan Python path zodat imports werken
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from fetcher import haal_alles_op
from ai_processor import verwerk_artikelen, genereer_markt_commentaar
from stock_fetcher import haal_aandelen_op
from pdf_generator import genereer_pdf
from emailer import stuur_email

# Logging configuratie
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("nieuwsagent")


def genereer_en_stuur(editie: str) -> None:
    """
    Hoofdfunctie: haal nieuws op, verwerk met AI, genereer PDF en stuur per email.

    Args:
        editie: "Ochtend", "Avond" of "Test"
    """
    config = load_config()

    # Datum in Nederlands formaat
    from babel.dates import format_date
    try:
        datum = format_date(datetime.date.today(), format="d MMMM yyyy", locale="nl")
    except Exception:
        datum = datetime.date.today().strftime("%d-%m-%Y")

    logger.info(f"═══ NieuwsAgent gestart — {datum} {editie} editie ═══")

    # Stap 1: Nieuws ophalen
    logger.info("Stap 1/5: Nieuws ophalen van RSS-bronnen...")
    artikelen = haal_alles_op()
    logger.info(f"  → {len(artikelen)} artikelen opgehaald")

    if not artikelen:
        logger.error("Geen artikelen opgehaald. Afbreken.")
        return

    # Stap 2: AI verwerking
    logger.info("Stap 2/5: AI verwerking (scoren + samenvatten)...")
    geselecteerd = verwerk_artikelen(artikelen, config)
    tech_count = len(geselecteerd.get("tech", []))
    nationaal_count = len(geselecteerd.get("nationaal", []))
    internationaal_count = len(geselecteerd.get("internationaal", []))
    logger.info(f"  → Geselecteerd: {tech_count} tech, {nationaal_count} nationaal, {internationaal_count} internationaal")

    # Stap 3: Aandelen ophalen
    logger.info("Stap 3/5: Aandelen ophalen...")
    aandelen = haal_aandelen_op()
    logger.info(f"  → {len(aandelen)} aandelen opgehaald")

    logger.info("Stap 3b: Marktcommentaar genereren...")
    try:
        markt_commentaar = genereer_markt_commentaar(aandelen, config)
        logger.info(f"  → Marktcommentaar: {len(markt_commentaar)} tekens")
    except Exception as e:
        logger.warning(f"Marktcommentaar mislukt: {e}")
        markt_commentaar = ""

    # Stap 4: PDF genereren
    logger.info("Stap 4/5: PDF genereren...")
    template_data = {
        "datum": datum,
        "editie": editie,
        "tech_artikelen": geselecteerd.get("tech", []),
        "nationaal_artikelen": geselecteerd.get("nationaal", []),
        "internationaal_artikelen": geselecteerd.get("internationaal", []),
        "aandelen": aandelen,
        "markt_commentaar": markt_commentaar,
    }
    try:
        pdf_bytes = genereer_pdf(template_data)
        logger.info(f"  → PDF: {len(pdf_bytes)//1024}KB")
    except Exception as e:
        logger.error(f"PDF generatie mislukt: {e}", exc_info=True)
        return

    # Stap 5: Email versturen
    logger.info("Stap 5/5: Email versturen...")
    try:
        stuur_email(pdf_bytes, config, editie, datum)
        logger.info(f"═══ NieuwsAgent klaar — {datum} {editie} editie verstuurd ═══")
    except Exception as e:
        logger.error(f"Email versturen mislukt: {e}", exc_info=True)


if __name__ == "__main__":
    editie = sys.argv[1] if len(sys.argv) > 1 else "Ochtend"
    genereer_en_stuur(editie)
