"""
stock_fetcher.py — Haalt beurskoersen op via yfinance.

Ondersteunde symbolen: S&P 500, grote tech-aandelen en Bitcoin.
Geeft een lijst van gestandaardiseerde dicts terug.
"""

import logging
import threading
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

AANDELEN: list[tuple[str, str]] = [
    ("^GSPC", "S&P 500"),
    ("NVDA", "Nvidia"),
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("GOOGL", "Google"),
    ("AMZN", "Amazon"),
    ("META", "Meta"),
    ("TSLA", "Tesla"),
    ("NFLX", "Netflix"),
    ("AMD", "AMD"),
    ("BTC-USD", "Bitcoin"),
]

# Maximale wachttijd per enkel yfinance-verzoek (seconden)
_FETCH_TIMEOUT_SEC = 15


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------


def haal_aandelen_op() -> list[dict]:
    """
    Haal actuele koersdata op voor alle gedefinieerde symbolen.

    Geeft een lijst van aandeel-dicts terug; symbolen waarbij het ophalen
    mislukt worden overgeslagen (met een waarschuwing in het logboek).
    """
    resultaten: list[dict] = []

    for ticker, naam in AANDELEN:
        try:
            info = _haal_ticker_info_op(ticker)
            if info is None:
                logger.warning("Geen data ontvangen voor %s (%s) — overgeslagen.", ticker, naam)
                continue

            aandeel = maak_aandeel_dict(ticker, naam, info)
            resultaten.append(aandeel)
            logger.debug(
                "Koers opgehaald: %s %s %s",
                naam,
                aandeel["prijs"],
                aandeel["wijziging_pct"],
            )
        except Exception:
            logger.exception(
                "Onverwachte fout bij ophalen van %s (%s) — overgeslagen.", ticker, naam
            )

    logger.info("%d van %d koersen succesvol opgehaald.", len(resultaten), len(AANDELEN))
    return resultaten


def maak_aandeel_dict(ticker: str, naam: str, info: dict) -> dict:
    """
    Bouw een gestandaardiseerde aandeel-dict op vanuit een info-dict.

    Parameters
    ----------
    ticker : str
        Beurssymbool (bijv. "AAPL").
    naam : str
        Leesbare naam (bijv. "Apple").
    info : dict
        Dict met minimaal de sleutels ``prijs`` (float) en ``wijziging`` (float, dag %).

    Geeft een dict terug met:
        ticker, naam, prijs (str), wijziging (float), wijziging_pct (str), kleur (str)
    """
    prijs_raw: float = info.get("prijs", 0.0) or 0.0
    wijziging_raw: float = info.get("wijziging", 0.0) or 0.0
    hoog_52w_raw: float = info.get("hoog_52w", 0.0) or 0.0
    laag_52w_raw: float = info.get("laag_52w", 0.0) or 0.0

    prijs_str = f"${prijs_raw:,.2f}"

    teken = "+" if wijziging_raw >= 0 else ""
    wijziging_pct_str = f"{teken}{wijziging_raw:.1f}%"

    if wijziging_raw > 0:
        kleur = "groen"
    elif wijziging_raw < 0:
        kleur = "rood"
    else:
        kleur = "grijs"

    afstand_hoog = ""
    if hoog_52w_raw and prijs_raw:
        pct = ((prijs_raw - hoog_52w_raw) / hoog_52w_raw) * 100
        afstand_hoog = f"{pct:+.0f}% v. 52w hoog"

    return {
        "ticker": ticker,
        "naam": naam,
        "prijs": prijs_str,
        "wijziging": round(wijziging_raw, 4),
        "wijziging_pct": wijziging_pct_str,
        "kleur": kleur,
        "hoog_52w": f"${hoog_52w_raw:,.2f}" if hoog_52w_raw else "–",
        "laag_52w": f"${laag_52w_raw:,.2f}" if laag_52w_raw else "–",
        "afstand_hoog": afstand_hoog,
    }


# ---------------------------------------------------------------------------
# Interne helpers
# ---------------------------------------------------------------------------


def _haal_ticker_info_op(ticker: str) -> Optional[dict]:
    """
    Haal prijs en dagwijziging op voor één ticker via yfinance.

    Gebruikt een threading.Timer als time-out mechanisme zodat hangende
    netwerkaanroepen het programma niet blokkeren.

    Geeft None terug als het ophalen mislukt of te lang duurt.
    """
    result_container: dict = {}
    error_container: dict = {}

    def _fetch():
        try:
            ticker_obj = yf.Ticker(ticker)
            # fast_info is lichter dan .info en geeft actuele koersdata
            fast = ticker_obj.fast_info

            prijs: Optional[float] = None
            wijziging: Optional[float] = None

            # Probeer actuele prijs
            try:
                prijs = float(fast.last_price)
            except (AttributeError, TypeError, ValueError):
                prijs = None

            # Probeer vorige slotkoers voor dagwijziging
            try:
                vorige_slotkoers = float(fast.previous_close)
                if vorige_slotkoers and vorige_slotkoers != 0 and prijs is not None:
                    wijziging = ((prijs - vorige_slotkoers) / vorige_slotkoers) * 100
            except (AttributeError, TypeError, ValueError, ZeroDivisionError):
                wijziging = None

            # Fallback: gebruik historische data van gisteren als fast_info leeg is
            if prijs is None:
                hist = ticker_obj.history(period="2d")
                if not hist.empty:
                    prijs = float(hist["Close"].iloc[-1])
                    if len(hist) >= 2:
                        vorige = float(hist["Close"].iloc[-2])
                        if vorige != 0:
                            wijziging = ((prijs - vorige) / vorige) * 100

            if prijs is None:
                error_container["msg"] = f"Geen prijsdata beschikbaar voor {ticker}"
                return

            result_container["prijs"] = prijs
            result_container["wijziging"] = wijziging if wijziging is not None else 0.0

            # 52-weeks hoog/laag
            try:
                result_container["hoog_52w"] = float(fast.year_high)
            except (AttributeError, TypeError, ValueError):
                result_container["hoog_52w"] = 0.0
            try:
                result_container["laag_52w"] = float(fast.year_low)
            except (AttributeError, TypeError, ValueError):
                result_container["laag_52w"] = 0.0

        except Exception as exc:
            error_container["exc"] = exc

    thread = threading.Thread(target=_fetch, daemon=True)
    thread.start()
    thread.join(timeout=_FETCH_TIMEOUT_SEC)

    if thread.is_alive():
        logger.warning("Time-out (%ds) bij ophalen van %s.", _FETCH_TIMEOUT_SEC, ticker)
        return None

    if "exc" in error_container:
        raise error_container["exc"]

    if "msg" in error_container:
        logger.warning(error_container["msg"])
        return None

    return result_container if result_container else None
