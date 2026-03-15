"""
ai_processor.py — Verwerkt nieuwsartikelen via de lokale Ollama API.

Functies:
- score_artikel: bepaal relevantie-score (1-10) voor een artikel
- bereken_tier: zet score om naar layout-tier (hero/feature/compact)
- genereer_samenvatting: maak een Nederlandse krantsamenvatting (tier-afhankelijke lengte)
- genereer_pull_quote: genereer een pakkende pull-quote zin voor hero-artikelen
- genereer_markt_commentaar: journalistiek marktcommentaar over koersbewegingen
- verwerk_artikelen: hoofdfunctie die alle artikelen scoort, tiert, selecteert en samenvat
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


def bereken_tier(score: float) -> str:
    """Bepaal layout-tier op basis van AI-score."""
    if score >= 9.0:
        return "hero"
    elif score >= 7.0:
        return "feature"
    else:
        return "compact"


_DOELLENGTE = {
    "hero":    "250 tot 300 woorden",
    "feature": "120 tot 150 woorden",
    "compact": "60 tot 80 woorden",
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
    categorie = artikel.get("categorie", "tech")
    samenvatting = artikel.get("samenvatting", "")

    if categorie == "tech":
        prompt = (
            "Beoordeel dit tech-nieuwsartikel op relevantie voor een tech-liefhebber.\n"
            "Geef een score van 1-10 waarbij 10 = baanbrekend tech nieuws.\n"
            "Antwoord ALLEEN met een getal tussen 1 en 10, niets anders.\n"
            "\n"
            f"Titel: {titel}\n"
            f"Beschrijving: {samenvatting}"
        )
    else:
        prompt = (
            "Beoordeel dit nieuwsartikel op relevantie en maatschappelijke impact.\n"
            "Geef een score van 1-10 waarbij 10 = zeer belangrijk nieuws.\n"
            "Antwoord ALLEEN met een getal tussen 1 en 10, niets anders.\n"
            "\n"
            f"Titel: {titel}\n"
            f"Beschrijving: {samenvatting}"
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

        match = re.search(r"\d+(?:[.,]\d+)?", tekst)
        if match:
            score = float(match.group(0).replace(",", "."))
            return max(1.0, min(10.0, score))

        logger.warning(
            "Geen getal gevonden in Ollama-antwoord voor artikel '%s': %r", titel, tekst
        )
        return 5.0

    except Exception as exc:
        logger.error(
            "Fout bij scoren van artikel '%s': %s — standaardscore 5.0 gebruikt", titel, exc
        )
        return 5.0


def genereer_samenvatting(artikel: dict, config: dict, tier: str = "compact") -> str:
    """
    Vraag Ollama om een Nederlandse krantsamenvatting van het artikel.

    Parameters
    ----------
    artikel : dict
        Artikeldict met minimaal 'titel', 'bron' en 'samenvatting'.
    config : dict
        Configuratiedict met 'ollama_url' en 'ollama_model'.
    tier : str
        'hero', 'feature' of 'compact' — bepaalt de doellengte.

    Returns
    -------
    str
        Nederlandse samenvatting; bij een fout de originele samenvatting.
    """
    ollama_url = config.get("ollama_url", "http://homeassistant:11434")
    ollama_model = config.get("ollama_model", "qwen2.5:3b")

    titel = artikel.get("titel", "")
    bron = artikel.get("bron", "")
    originele_samenvatting = artikel.get("samenvatting", "")

    tekst = artikel.get("volledige_tekst") or originele_samenvatting
    max_chars = 3000 if tier == "hero" else 2000
    tekst = tekst[:max_chars]

    doellengte = _DOELLENGTE.get(tier, "100 tot 150 woorden")

    prompt = (
        f"Jij bent een Nederlandse nieuwsredacteur. Schrijf een samenvatting van {doellengte}.\n"
        "\n"
        "Regels:\n"
        "- Behoud de toon en schrijfstijl van het originele artikel zo veel mogelijk\n"
        "- Journalistieke stijl: directe zinnen, actieve werkwoorden\n"
        "- Schrijf in het Nederlands\n"
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

        logger.warning("Lege samenvatting ontvangen van Ollama voor artikel '%s'", titel)

    except Exception as exc:
        logger.error(
            "Fout bij genereren samenvatting voor artikel '%s': %s — origineel gebruikt",
            titel, exc,
        )

    woorden = originele_samenvatting.split()
    return " ".join(woorden[:250])


def genereer_pull_quote(artikel: dict, config: dict) -> str:
    """
    Genereer een pakkende pull-quote zin (max 20 woorden) voor hero-artikelen.

    Returns een lege string bij een fout.
    """
    ollama_url = config.get("ollama_url", "http://homeassistant:11434")
    ollama_model = config.get("ollama_model", "qwen2.5:3b")

    titel = artikel.get("titel", "")
    tekst = (artikel.get("volledige_tekst") or artikel.get("samenvatting_nl") or "")[:1500]

    prompt = (
        "Schrijf één pakkende zin van maximaal 20 woorden die de kern van dit artikel vangt.\n"
        "De zin moet opvallen als pull-quote in een magazine.\n"
        "Antwoord ALLEEN met de zin, geen aanhalingstekens, geen uitleg.\n"
        "\n"
        f"Artikel: {titel}\n"
        f"Tekst: {tekst}"
    )

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as exc:
        logger.error("Fout bij pull-quote voor '%s': %s", titel, exc)
        return ""


def genereer_markt_commentaar(aandelen: list[dict], config: dict) -> str:
    """
    Genereer 3-4 zinnen journalistiek marktcommentaar over de dagelijkse bewegingen.

    Returns een lege string bij een fout.
    """
    ollama_url = config.get("ollama_url", "http://homeassistant:11434")
    ollama_model = config.get("ollama_model", "qwen2.5:3b")

    if not aandelen:
        return ""

    overzicht = "\n".join(
        f"{a['naam']}: {a['prijs']} ({a['wijziging_pct']})" for a in aandelen
    )

    prompt = (
        "Jij bent een financieel journalist. Schrijf 3 tot 4 zinnen marktcommentaar "
        "over de onderstaande koersbewegingen van vandaag.\n"
        "Noem de grootste winnaars en verliezers bij naam. "
        "Journalistieke stijl. Schrijf in het Nederlands. Geen bullet points.\n"
        "\n"
        f"Koersen:\n{overzicht}\n\nMarktcommentaar:"
    )

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=90,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as exc:
        logger.error("Fout bij marktcommentaar: %s", exc)
        return ""


def verwerk_artikelen(artikelen: list[dict], config: dict) -> dict:
    """
    Verwerk alle artikelen: scoor, tier, selecteer en vat samen.

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
        Elk artikel heeft extra sleutels: 'score', 'tier', 'samenvatting_nl', 'pull_quote'.
    """
    logger.info("Start verwerking van %d artikelen", len(artikelen))

    # Stap 1: Score elk artikel
    for index, artikel in enumerate(artikelen, start=1):
        score = score_artikel(artikel, config)
        artikel["score"] = score
        logger.debug(
            "Artikel %d/%d gescoord: '%.30s...' → %.1f",
            index, len(artikelen), artikel.get("titel", ""), score,
        )

    logger.info("Alle %d artikelen gescoord", len(artikelen))

    # Stap 2: Tiers toewijzen op basis van score
    for artikel in artikelen:
        artikel["tier"] = bereken_tier(artikel.get("score", 5.0))

    # Stap 3: Sorteer per categorie en selecteer de top-N
    resultaat: dict = {categorie: [] for categorie in _SELECTIE}

    for categorie, max_aantal in _SELECTIE.items():
        artikelen_in_categorie = [a for a in artikelen if a.get("categorie") == categorie]
        gesorteerd = sorted(artikelen_in_categorie, key=lambda a: a.get("score", 0.0), reverse=True)
        geselecteerd = gesorteerd[:max_aantal]
        resultaat[categorie] = geselecteerd
        logger.info(
            "Categorie '%s': %d beschikbaar, %d geselecteerd",
            categorie, len(artikelen_in_categorie), len(geselecteerd),
        )

    # Stap 4: Genereer samenvattingen + pull quotes voor geselecteerde artikelen
    totaal = sum(len(v) for v in resultaat.values())
    teller = 0

    for categorie, geselecteerde_artikelen in resultaat.items():
        for artikel in geselecteerde_artikelen:
            teller += 1
            tier = artikel.get("tier", "compact")
            logger.info(
                "Samenvatting genereren %d/%d [%s]: '%s'",
                teller, totaal, tier, artikel.get("titel", ""),
            )
            artikel["samenvatting_nl"] = genereer_samenvatting(artikel, config, tier=tier)

            if tier == "hero":
                logger.info("Pull-quote genereren voor: '%s'", artikel.get("titel", ""))
                artikel["pull_quote"] = genereer_pull_quote(artikel, config)
            else:
                artikel["pull_quote"] = ""

    logger.info(
        "Verwerking voltooid: %d artikelen gescoord, %d geselecteerd en samengevat",
        len(artikelen), totaal,
    )

    return resultaat
