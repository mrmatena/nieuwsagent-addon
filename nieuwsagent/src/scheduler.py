import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

def start_scheduler(genereer_en_stuur_fn, config: dict) -> None:
    """
    Start de APScheduler met twee dagelijkse taken (ochtend + avond).
    Draait ook direct een test-run bij opstarten.
    Blokkeert de main thread totdat het programma stopt.

    Args:
        genereer_en_stuur_fn: callable die editie (str) als argument neemt
        config: configuratie dict
    """
    scheduler = BlockingScheduler(timezone="Europe/Amsterdam")

    # Parse tijdstippen met fallback bij ongeldige waarden
    try:
        ochtend_parts = config.get("tijdstip_ochtend", "06:00").split(":")
        ochtend_uur = int(ochtend_parts[0])
        ochtend_min = int(ochtend_parts[1])
    except (ValueError, IndexError):
        logger.warning("Ongeldig tijdstip_ochtend in configuratie, gebruik standaard 06:00")
        ochtend_uur, ochtend_min = 6, 0

    try:
        avond_parts = config.get("tijdstip_avond", "17:00").split(":")
        avond_uur = int(avond_parts[0])
        avond_min = int(avond_parts[1])
    except (ValueError, IndexError):
        logger.warning("Ongeldig tijdstip_avond in configuratie, gebruik standaard 17:00")
        avond_uur, avond_min = 17, 0

    scheduler.add_job(
        lambda: genereer_en_stuur_fn("Ochtend"),
        CronTrigger(hour=ochtend_uur, minute=ochtend_min, timezone="Europe/Amsterdam"),
        id="ochtend_krant",
        name=f"Ochtendkrant {ochtend_uur:02d}:{ochtend_min:02d}"
    )

    scheduler.add_job(
        lambda: genereer_en_stuur_fn("Avond"),
        CronTrigger(hour=avond_uur, minute=avond_min, timezone="Europe/Amsterdam"),
        id="avond_krant",
        name=f"Avondkrant {avond_uur:02d}:{avond_min:02d}"
    )

    logger.info(
        f"Scheduler gestart: ochtend {ochtend_uur:02d}:{ochtend_min:02d}, "
        f"avond {avond_uur:02d}:{avond_min:02d} (Europe/Amsterdam)"
    )

    # Direct een test-run bij opstarten
    logger.info("Directe test-run bij opstarten...")
    try:
        genereer_en_stuur_fn("Test")
    except Exception as e:
        logger.error(f"Test-run mislukt: {e}")

    # Blokkeer de main thread
    scheduler.start()
