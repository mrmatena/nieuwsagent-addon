import os
import tempfile
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger(__name__)

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
