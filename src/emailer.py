import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

logger = logging.getLogger(__name__)

def stuur_email(pdf_bytes: bytes, config: dict, editie: str, datum: str) -> None:
    """
    Verstuurt de nieuwskrant PDF per email via Gmail SMTP.

    Args:
        pdf_bytes: PDF bestand als bytes
        config: configuratie dict met gmail_address, gmail_app_password, ontvanger_email
        editie: "Ochtend", "Avond" of "Test"
        datum: datum string bijv "15 maart 2026"

    Raises:
        Exception bij verbindings- of verzendfouten
    """
    verzender = config["gmail_address"]
    ontvanger = config["ontvanger_email"]
    onderwerp = f"De NieuwsAgent — {datum} ({editie})"

    msg = MIMEMultipart()
    msg["From"] = verzender
    msg["To"] = ontvanger
    msg["Subject"] = onderwerp

    # Bodytekst
    bodytekst = (
        f"Goedemorgen!\n\n"
        f"Uw dagelijkse nieuwskrant voor {datum} ({editie} editie) is bijgevoegd.\n\n"
        f"— De NieuwsAgent"
    )
    msg.attach(MIMEText(bodytekst, "plain", "utf-8"))

    # PDF bijlage
    bestandsnaam = f"nieuwsagent_{datum.replace(' ', '_')}_{editie}.pdf"
    bijlage = MIMEBase("application", "pdf")
    bijlage.set_payload(pdf_bytes)
    encoders.encode_base64(bijlage)
    bijlage.add_header(
        "Content-Disposition",
        f'attachment; filename="{bestandsnaam}"'
    )
    msg.attach(bijlage)

    # Verstuur via Gmail SMTP
    logger.info(f"Email versturen naar {ontvanger} via smtp.gmail.com:587")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(verzender, config["gmail_app_password"])
        server.send_message(msg)

    logger.info(f"Email verstuurd: '{onderwerp}' → {ontvanger}")
