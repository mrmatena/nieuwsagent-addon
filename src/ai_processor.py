"""
ai_processor.py — Verwerkt nieuwsartikelen via de lokale Ollama API.

Functies:
- score_artikel: bepaal relevantie-score (1-10) voor een artikel
- genereer_samenvatting: maak een Nederlandse krantsamenvatting
- verwerk_artikelen: hoofdfunctie die alle artikelen scoort, selecteert en samenvat
"""

import logging
import re

import requests

logger = logging.getLogger(__name__)

# Aantal te selecteren artikelen per categorie
_SELECTIE = {
    "tech": 9,
    "nationaal": 4,
    "internationaal": 4,
}


def score_artikel(artikel: dict, config: dict) -> float:
    """
    Vraag Ollama om een relevantie-score (1-10) voor het artikel.

    Parameters
    ----------
    artikel : dict
        Artikeldict met minimaal 'titel', 'categorie' en 'samenvatting'.
    config : dict
        Configuratiedict met 'ollama_url' en 'ollama_model'.

    Returns
    -------
    float
        Score tussen 1.0 en 10.0; bij een fout wordt 5.0 teruggegeven.
    """
    ollama_url = config.get("ollama_url", "http://homeassistant:11434")
    ollama_model = config.get("ollama_model", "qwen2.5:3b")

    titel = artikel.get("titel", "")
    categorie = artikel.get("categorie", "")
    samenvatting = artikel.get("samenvatting", "")

    prompt = (
        "Beoordeel dit nieuwsartikel op relevantie voor een tech-liefhebber.\n"
        "Geef een score van 1-10 waarbij 10 = zeer relevant tech nieuws.\n"
        "Antwoord ALLEEN met een getal tussen 1 en 10, niets anders.\n"
        "\n"
        f"Titel: {titel}\n"
        f"Categorie: {categorie}\n"
        f"Korte beschrijving: {samenvatting}"
    )

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        tekst = data.get("response", "")

        # Extraheer het eerste getal uit de response
        match = re.search(r"\d+(?:[.,]\d+)?", tekst)
        if match:
            score = float(match.group(0).replace(",", "."))
            # Zorg dat de score binnen het geldige bereik valt
            return max(1.0, min(10.0, score))

        logger.warning(
            "Geen getal gevonden in Ollama-antwoord voor artikel '%s': %r",
            titel,
            tekst,
        )
        return 5.0

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Fout bij scoren van artikel '%s': %s — standaardscore 5.0 gebruikt",
            titel,
            exc,
        )
        return 5.0


def genereer_samenvatting(artikel: dict, config: dict) -> str:
    """
    Vraag Ollama om een Nederlandse krantsamenvatting van het artikel.

    Parameters
    ----------
    artikel : dict
        Artikeldict met minimaal 'titel', 'bron' en 'samenvatting'.
        Optioneel: 'volledige_tekst'.
    config : dict
        Configuratiedict met 'ollama_url' en 'ollama_model'.

    Returns
    -------
    str
        Nederlandse samenvatting; bij een fout de originele samenvatting
        (eerste 250 woorden).
    """
    ollama_url = config.get("ollama_url", "http://homeassistant:11434")
    ollama_model = config.get("ollama_model", "qwen2.5:3b")

    titel = artikel.get("titel", "")
    bron = artikel.get("bron", "")
    originele_samenvatting = artikel.get("samenvatting", "")

    # Gebruik volledige_tekst indien beschikbaar, anders samenvatting
    tekst = artikel.get("volledige_tekst") or originele_samenvatting

    # Beperk invoertekst tot 2000 tekens
    tekst = tekst[:2000]

    prompt = (
        "Jij bent een Nederlandse nieuwsredacteur. Schrijf een samenvatting van dit artikel "
        "in het Nederlands, in journalistieke krantstijl.\n"
        "\n"
        "Regels:\n"
        "- Maximaal 200 woorden\n"
        "- Schrijf in het Nederlands, ook als het origineel in het Engels is\n"
        "- Directe, informatieve schrijfstijl\n"
        "- Geen bullet points, gewone alinea's\n"
        f"- Vermeld de bron ({bron}) niet in de tekst\n"
        "\n"
        f"Titel: {titel}\n"
        "Originele tekst:\n"
        f"{tekst}\n"
        "\n"
        "Schrijf de Nederlandse samenvatting:"
    )

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        samenvatting = data.get("response", "").strip()

        if samenvatting:
            return samenvatting

        logger.warning(
            "Lege samenvatting ontvangen van Ollama voor artikel '%s'", titel
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Fout bij genereren samenvatting voor artikel '%s': %s — origineel gebruikt",
            titel,
            exc,
        )

    # Fallback: eerste 250 woorden van de originele samenvatting
    woorden = originele_samenvatting.split()
    return " ".join(woorden[:250])


def verwerk_artikelen(artikelen: list[dict], config: dict) -> dict:
    """
    Verwerk alle artikelen: scoor, selecteer en vat samen.

    Parameters
    ----------
    artikelen : list[dict]
        Lijst met artikeldicts. Elk dict heeft minimaal 'categorie'.
    config : dict
        Configuratiedict.

    Returns
    -------
    dict
        {"tech": [...], "nationaal": [...], "internationaal": [...]}
        Elk artikel in de lijsten heeft een extra 'score' en 'samenvatting_nl' sleutel.
    """
    logger.info("Start verwerking van %d artikelen", len(artikelen))

    # Stap 1: Score elk artikel
    for index, artikel in enumerate(artikelen, start=1):
        score = score_artikel(artikel, config)
        artikel["score"] = score
        logger.debug(
            "Artikel %d/%d gescoord: '%.30s...' → %.1f",
            index,
            len(artikelen),
            artikel.get("titel", ""),
            score,
        )

    logger.info("Alle %d artikelen gescoord", len(artikelen))

    # Stap 2 & 3: Sorteer per categorie en selecteer de top-N
    resultaat: dict = {categorie: [] for categorie in _SELECTIE}

    for categorie, max_aantal in _SELECTIE.items():
        artikelen_in_categorie = [
            a for a in artikelen if a.get("categorie") == categorie
        ]
        gesorteerd = sorted(
            artikelen_in_categorie, key=lambda a: a.get("score", 0.0), reverse=True
        )
        geselecteerd = gesorteerd[:max_aantal]
        resultaat[categorie] = geselecteerd
        logger.info(
            "Categorie '%s': %d artikelen beschikbaar, %d geselecteerd",
            categorie,
            len(artikelen_in_categorie),
            len(geselecteerd),
        )

    # Stap 4: Genereer Nederlandse samenvattingen voor geselecteerde artikelen
    totaal_geselecteerd = sum(len(v) for v in resultaat.values())
    teller = 0

    for categorie, geselecteerde_artikelen in resultaat.items():
        for artikel in geselecteerde_artikelen:
            teller += 1
            logger.info(
                "Samenvatting genereren %d/%d: '%s'",
                teller,
                totaal_geselecteerd,
                artikel.get("titel", ""),
            )
            samenvatting_nl = genereer_samenvatting(artikel, config)
            artikel["samenvatting_nl"] = samenvatting_nl

    logger.info(
        "Verwerking voltooid: %d artikelen gescoord, %d geselecteerd en samengevat",
        len(artikelen),
        totaal_geselecteerd,
    )

    return resultaat
