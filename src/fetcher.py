"""
fetcher.py — Haalt RSS-feeds op en scrapet volledige artikelinhoud.

Verantwoordelijkheden:
- RSS-feeds ophalen via feedparser
- Volledige artikeltekst scrapen via requests + BeautifulSoup
- Afbeeldingen downloaden naar tijdelijke bestanden
- Deduplicatie op URL
"""

import logging
import os
import tempfile
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

RSS_SOURCES = [
    # Tech (80% gewicht) — alleen Nederlandse bronnen
    {"url": "https://feeds.tweakers.net/nieuws/top.rss", "categorie": "tech", "taal": "nl", "naam": "Tweakers"},
    {"url": "https://www.bright.nl/feed/news.xml", "categorie": "tech", "taal": "nl", "naam": "Bright"},
    # Nationaal (10% gewicht)
    {"url": "https://feeds.nos.nl/nosnieuwsalgemeen", "categorie": "nationaal", "taal": "nl", "naam": "NOS"},
    {"url": "https://www.nu.nl/rss/Algemeen", "categorie": "nationaal", "taal": "nl", "naam": "Nu.nl"},
    # Internationaal (10% gewicht)
    {"url": "https://feeds.nos.nl/nosnieuwsbuitenland", "categorie": "internationaal", "taal": "nl", "naam": "NOS Buitenland"},
]

_IMG_DIR = "/tmp/nieuwsagent_imgs"
_MAX_ARTIKELEN_PER_BRON = 15
_MAX_TEKST_CHARS = 10_000
_MAX_SAMENVATTING_CHARS = 500

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _zorg_voor_img_dir() -> None:
    """Maak de tijdelijke afbeeldingenmap aan als die nog niet bestaat."""
    os.makedirs(_IMG_DIR, exist_ok=True)


def _strip_html(tekst: str) -> str:
    """Verwijder HTML-tags uit een string via BeautifulSoup."""
    if not tekst:
        return ""
    soup = BeautifulSoup(tekst, "lxml")
    return soup.get_text(separator=" ", strip=True)


def _haal_afbeelding_url_uit_entry(entry) -> str | None:
    """Probeer een afbeeldings-URL te vinden in de feedparser entry."""
    # 1. Enclosures (bijv. <enclosure type="image/...">)
    for enc in getattr(entry, "enclosures", []):
        mime = getattr(enc, "type", "") or ""
        if mime.startswith("image/"):
            url = getattr(enc, "href", None) or getattr(enc, "url", None)
            if url:
                return url

    # 2. media:content / media:thumbnail (feedparser slaat dit op in media_content)
    for media in getattr(entry, "media_content", []):
        mime = media.get("type", "") or ""
        url = media.get("url", "")
        if url and (mime.startswith("image/") or not mime):
            return url

    # 3. media:thumbnail
    thumbnail = getattr(entry, "media_thumbnail", None)
    if thumbnail:
        if isinstance(thumbnail, list) and thumbnail:
            url = thumbnail[0].get("url", "")
            if url:
                return url

    return None


# ---------------------------------------------------------------------------
# Publieke functies
# ---------------------------------------------------------------------------


def fetch_rss(source: dict) -> list[dict]:
    """
    Haal de RSS feed van één bron op via feedparser.

    Parameters
    ----------
    source : dict
        Een entry uit RSS_SOURCES met minimaal de sleutels
        'url', 'naam', 'categorie' en 'taal'.

    Returns
    -------
    list[dict]
        Lijst van artikel-dicts. Leeg bij een fout.
    """
    try:
        # feedparser heeft geen ingebouwde timeout; gebruik requests om de feed
        # op te halen en geef de inhoud door aan feedparser.
        resp = requests.get(source["url"], timeout=10, headers=_HEADERS)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as exc:
        logger.warning("Kon RSS feed niet ophalen voor '%s': %s", source["naam"], exc)
        return []

    artikelen: list[dict] = []

    for entry in feed.entries[:_MAX_ARTIKELEN_PER_BRON]:
        try:
            # Titel
            titel = getattr(entry, "title", "") or ""

            # URL
            url = getattr(entry, "link", "") or ""

            # Samenvatting — strip HTML, beperk lengte
            samenvatting_raw = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or ""
            )
            samenvatting = _strip_html(samenvatting_raw)[:_MAX_SAMENVATTING_CHARS]

            # Publicatiedatum — altijd als ISO string opslaan voor template-compatibiliteit
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    gepubliceerd = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    gepubliceerd = getattr(entry, "published", "") or ""
            else:
                gepubliceerd = getattr(entry, "published", "") or ""

            # Afbeelding uit RSS (optioneel)
            afbeelding_url = _haal_afbeelding_url_uit_entry(entry)

            artikelen.append(
                {
                    "titel": titel,
                    "url": url,
                    "samenvatting": samenvatting,
                    "gepubliceerd": gepubliceerd,
                    "bron": source["naam"],
                    "categorie": source["categorie"],
                    "taal": source["taal"],
                    "afbeelding_url": afbeelding_url,
                }
            )
        except Exception as exc:
            logger.warning(
                "Fout bij verwerken van entry uit '%s': %s", source["naam"], exc
            )
            continue

    logger.info(
        "Opgehaald: %d artikelen van '%s'", len(artikelen), source["naam"]
    )
    return artikelen


def scrape_artikel(url: str) -> dict:
    """
    Scrape de volledige tekst en hoofdafbeelding van een artikel-URL.

    Parameters
    ----------
    url : str
        De URL van het artikel.

    Returns
    -------
    dict
        Dict met 'volledige_tekst' (str) en 'afbeelding_pad' (str | None).
        Leeg dict bij een fout.
    """
    try:
        resp = requests.get(url, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        # ------------------------------------------------------------------ #
        # Tekst extraheren
        # ------------------------------------------------------------------ #
        tekst_container = None

        # 1. Zoek naar <article>
        article_tag = soup.find("article")
        if article_tag:
            tekst_container = article_tag

        # 2. Zoek het element met de meeste <p>-tags
        if tekst_container is None:
            beste_kandidaat = None
            max_p = 0
            for tag in soup.find_all(True):
                p_count = len(tag.find_all("p", recursive=False))
                if p_count > max_p:
                    max_p = p_count
                    beste_kandidaat = tag
            tekst_container = beste_kandidaat

        if tekst_container:
            volledige_tekst = tekst_container.get_text(separator="\n", strip=True)
        else:
            volledige_tekst = soup.get_text(separator="\n", strip=True)

        volledige_tekst = volledige_tekst[:_MAX_TEKST_CHARS]

        # ------------------------------------------------------------------ #
        # Afbeelding extraheren en downloaden
        # ------------------------------------------------------------------ #
        afbeelding_pad: str | None = None

        zoek_context = tekst_container if tekst_container else soup
        for img in zoek_context.find_all("img"):
            src = img.get("src", "") or ""

            # Moet een absolute URL zijn
            if not (src.startswith("http://") or src.startswith("https://")):
                continue

            # Sla kleine thumbnails over op basis van width-attribuut
            width_attr = img.get("width", "")
            if width_attr:
                try:
                    if int(width_attr) < 200:
                        continue
                except (ValueError, TypeError):
                    pass

            # Eenvoudige heuristiek: sla src's over die typische thumbnail-tekens bevatten
            src_lower = src.lower()
            thumbnail_tekens = ("thumb", "icon", "avatar", "logo", "pixel", "1x1", "spacer")
            if any(t in src_lower for t in thumbnail_tekens):
                continue

            # Download de afbeelding
            try:
                _zorg_voor_img_dir()
                img_resp = requests.get(src, timeout=10, headers=_HEADERS)
                img_resp.raise_for_status()

                # Bepaal extensie op basis van Content-Type
                content_type = img_resp.headers.get("Content-Type", "image/jpeg")
                if "png" in content_type:
                    suffix = ".png"
                elif "gif" in content_type:
                    suffix = ".gif"
                elif "webp" in content_type:
                    suffix = ".webp"
                else:
                    suffix = ".jpg"

                fd, pad = tempfile.mkstemp(suffix=suffix, dir=_IMG_DIR)
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(img_resp.content)
                    afbeelding_pad = pad
                except Exception:
                    os.close(fd)
                    raise

                break  # Eerste geschikte afbeelding gevonden
            except Exception as exc:
                logger.warning("Kon afbeelding niet downloaden van '%s': %s", src, exc)
                continue

        return {
            "volledige_tekst": volledige_tekst,
            "afbeelding_pad": afbeelding_pad,
        }

    except Exception as exc:
        logger.warning("Kon artikel niet scrapen ('%s'): %s", url, exc)
        return {}


def haal_alles_op() -> list[dict]:
    """
    Haal alle RSS-feeds op en verrijk elk artikel met gescrapete inhoud.

    Returns
    -------
    list[dict]
        Gededupliceerde lijst van artikel-dicts, elk verrijkt met
        'volledige_tekst' en 'afbeelding_pad'.
    """
    alle_artikelen: list[dict] = []
    geziene_urls: set[str] = set()

    # RSS feeds ophalen
    for source in RSS_SOURCES:
        artikelen = fetch_rss(source)
        for artikel in artikelen:
            url = artikel.get("url", "")
            if url and url in geziene_urls:
                continue
            if url:
                geziene_urls.add(url)
            alle_artikelen.append(artikel)

    logger.info(
        "Totaal %d unieke artikelen opgehaald uit %d bronnen",
        len(alle_artikelen),
        len(RSS_SOURCES),
    )

    # Artikelen verrijken met gescrapete inhoud
    for i, artikel in enumerate(alle_artikelen):
        url = artikel.get("url", "")
        if not url:
            artikel["volledige_tekst"] = ""
            artikel["afbeelding_pad"] = None
            continue

        logger.debug("Scrapen artikel %d/%d: %s", i + 1, len(alle_artikelen), url)
        scrape_data = scrape_artikel(url)
        artikel["volledige_tekst"] = scrape_data.get("volledige_tekst", "")
        artikel["afbeelding_pad"] = scrape_data.get("afbeelding_pad", None)

    # Dedupliceer afbeeldingen op pad én op URL — elk plaatje mag maar één keer voorkomen
    gebruikte_afbeelding_paden: set[str] = set()
    gebruikte_afbeelding_urls: set[str] = set()
    for artikel in alle_artikelen:
        pad = artikel.get("afbeelding_pad")
        url = artikel.get("afbeelding_url")
        if pad and pad in gebruikte_afbeelding_paden:
            artikel["afbeelding_pad"] = None
            logger.debug("Dubbel afbeeldingspad verwijderd voor '%s'", artikel.get("titel", ""))
        elif url and url in gebruikte_afbeelding_urls:
            artikel["afbeelding_pad"] = None
            logger.debug("Dubbele afbeeldings-URL verwijderd voor '%s'", artikel.get("titel", ""))
        else:
            if pad:
                gebruikte_afbeelding_paden.add(pad)
            if url:
                gebruikte_afbeelding_urls.add(url)

    return alle_artikelen
