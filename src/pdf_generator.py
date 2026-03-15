import os
import tempfile
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Afbeeldingscompressie per tier
# ---------------------------------------------------------------------------

_COMPRESSED_DIR = "/tmp/nieuwsagent_imgs/compressed"

_TIER_IMG = {
    "hero":    {"max_breedte": 800, "kwaliteit": 70},
    "feature": {"max_breedte": 600, "kwaliteit": 70},
    "compact": {"max_breedte": 180, "kwaliteit": 65},
}


def comprimeer_afbeelding(pad: str, tier: str) -> str:
    """
    Comprimeer en schaal afbeelding naar tier-specifieke afmetingen.

    Geeft het pad naar de gecomprimeerde versie terug.
    Bij een fout wordt het originele pad teruggegeven.
    """
    os.makedirs(_COMPRESSED_DIR, exist_ok=True)
    cfg = _TIER_IMG.get(tier, _TIER_IMG["feature"])
    uitvoer = os.path.join(_COMPRESSED_DIR, os.path.basename(pad))
    try:
        with Image.open(pad) as img:
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            if img.width > cfg["max_breedte"]:
                ratio = cfg["max_breedte"] / img.width
                nieuw_formaat = (cfg["max_breedte"], int(img.height * ratio))
                img = img.resize(nieuw_formaat, Image.LANCZOS)
            img.save(uitvoer, "JPEG", quality=cfg["kwaliteit"], optimize=True)
        return uitvoer
    except Exception as exc:
        logger.warning("Compressie mislukt (%s): %s", pad, exc)
        return pad

TEMPLATES_DIR = Path(__file__).parent / "templates"

def render_html(template_data: dict) -> str:
    """Render de Jinja2 krant template naar HTML string."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("krant.html")
    return template.render(**template_data)

def genereer_pdf(template_data: dict) -> bytes:
    """
    Render het HTML template en converteer naar PDF bytes via WeasyPrint.
    Returns PDF als bytes.
    Raises Exception als het mislukt.
    """
    # Comprimeer alle afbeeldingen per tier vóór rendering
    for cat in ["tech_artikelen", "nationaal_artikelen", "internationaal_artikelen"]:
        for artikel in template_data.get(cat, []):
            tier = artikel.get("tier", "compact")
            paden = artikel.get("afbeelding_paden", [])
            artikel["afbeelding_paden"] = [
                comprimeer_afbeelding(p, tier) for p in paden if os.path.exists(p)
            ]

    html_content = render_html(template_data)

    # Schrijf HTML naar tijdelijk bestand (WeasyPrint leest lokale bestanden beter zo)
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.html',
        delete=False,
        encoding='utf-8',
        prefix='nieuwsagent_'
    ) as f:
        f.write(html_content)
        html_pad = f.name

    try:
        logger.info(f"WeasyPrint genereert PDF van {html_pad}")
        pdf_bytes = HTML(filename=html_pad).write_pdf()
        logger.info(f"PDF gegenereerd: {len(pdf_bytes)//1024}KB")
        return pdf_bytes
    finally:
        try:
            os.unlink(html_pad)
        except Exception:
            pass
