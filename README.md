# De NieuwsAgent

Een dagelijkse AI-gegenereerde nieuwskrant als PDF, twee keer per dag in je inbox. 80% tech nieuws, 10% nationaal, 10% internationaal — alles in het Nederlands, inclusief aandelenkoersen.

**Draait lokaal op je Mac** via Python + Ollama. Geen cloud, geen abonnementskosten.

---

## Wat heb je nodig?

- macOS op Apple Silicon (M1/M2/M3) of Intel Mac
- Python 3.11+ (standaard aanwezig op macOS)
- [Homebrew](https://brew.sh) (pakketbeheer voor macOS)
- Gmail-account met app-wachtwoord
- ~10GB schijfruimte (voor het AI-model)

---

## Installatie (eenmalig)

### Stap 1 — Homebrew systeembibliotheken

WeasyPrint (PDF-generator) heeft een aantal systeempakketten nodig:

```bash
brew install pango cairo gdk-pixbuf libffi
```

### Stap 2 — Ollama installeren + AI-model downloaden

```bash
brew install ollama
brew services start ollama          # autostart bij inloggen
ollama pull qwen2.5:14b             # ~9GB download, aanbevolen voor M1 16GB
```

> **Alternatief sneller model:** `ollama pull qwen2.5:7b` (~5GB, iets minder nauwkeurig)

### Stap 3 — Python dependencies installeren

```bash
cd /Users/martijnmatena/Projects/NieuwsAgent
pip3 install -r requirements.txt
```

### Stap 4 — Configuratie aanmaken

```bash
cp config.json.example config.json
open config.json
```

Vul in:

```json
{
  "gmail_address": "jouw@gmail.com",
  "gmail_app_password": "xxxx xxxx xxxx xxxx",
  "ontvanger_email": "jouw@gmail.com",
  "ollama_url": "http://localhost:11434",
  "ollama_model": "qwen2.5:14b"
}
```

**Gmail app-wachtwoord aanmaken:**
1. Ga naar [myaccount.google.com](https://myaccount.google.com) → Beveiliging
2. Zorg dat 2-stapsverificatie aan staat
3. Zoek "App-wachtwoorden" → Maak nieuw wachtwoord aan (naam: "NieuwsAgent")
4. Kopieer het 16-karakter wachtwoord (zonder spaties)

### Stap 5 — Automatisch plannen via launchd

```bash
# Kopieer de planningsbestanden
cp launchd/com.nieuwsagent.ochtend.plist ~/Library/LaunchAgents/
cp launchd/com.nieuwsagent.avond.plist ~/Library/LaunchAgents/

# Activeer (eenmalig na elke reboot/herinstallatie)
launchctl load ~/Library/LaunchAgents/com.nieuwsagent.ochtend.plist
launchctl load ~/Library/LaunchAgents/com.nieuwsagent.avond.plist
```

De krant wordt nu elke dag gegenereerd om **07:00** (Ochtend) en **17:00** (Avond).

### Optioneel — Mac automatisch wekken uit slaapstand

Als je Mac op netstroom staat, kan hij zichzelf wekken:

```bash
# Wek Mac elke dag om 06:55 (5 minuten voor de ochtendkrant)
sudo pmset repeat wakeorpoweron MTWRFSU 06:55:00
```

> ⚠️ Werkt alleen als de Mac is aangesloten aan stroom. Op batterij slaapt de Mac door.

---

## Direct testen

```bash
# Test meteen een volledige run (stuurt een email)
python3 src/main.py Ochtend

# Logs bekijken
tail -f ~/Library/Logs/nieuwsagent.log

# launchd handmatig triggeren (alsof het 07:00 is)
launchctl start com.nieuwsagent.ochtend
```

---

## Componenten controleren

```bash
# Ollama bereikbaar?
curl http://localhost:11434/api/tags

# RSS feeds werkend?
python3 -c "import sys; sys.path.insert(0,'src'); from fetcher import haal_alles_op; a = haal_alles_op(); print(len(a), 'artikelen')"

# Aandelen werkend?
python3 -c "import sys; sys.path.insert(0,'src'); from stock_fetcher import haal_aandelen_op; print(haal_aandelen_op())"
```

---

## Architectuur

```
RSS-feeds (7 bronnen)
  → AI scoring + NL samenvatting (Ollama qwen2.5:14b)
    → Aandelenkoersen (yfinance)
      → PDF (WeasyPrint + Jinja2)
        → Email (Gmail SMTP)
```

| Bestand | Doel |
|---------|------|
| `src/main.py` | Orchestrator — wordt aangeroepen door launchd |
| `src/config.py` | Laadt `config.json` of env vars |
| `src/fetcher.py` | RSS ophalen + artikel scrapen + afbeeldingen |
| `src/ai_processor.py` | Ollama client — scoren + Dutch samenvatting |
| `src/stock_fetcher.py` | S&P500 + 9 tech aandelen + Bitcoin |
| `src/pdf_generator.py` | HTML → PDF via WeasyPrint |
| `src/emailer.py` | Gmail SMTP met PDF bijlage |
| `src/templates/krant.html` | Jinja2 kranttemplate |
| `launchd/` | macOS planningsbestanden (07:00 + 17:00) |
| `config.json` | Jouw instellingen (niet in git) |

**RSS-bronnen:** Tweakers, The Verge, Engadget, MacRumors (tech) · NOS, Nu.nl (nationaal) · NOS Buitenland (internationaal)

**Aandelen:** S&P 500, Nvidia, Apple, Microsoft, Google, Amazon, Meta, Tesla, Netflix, AMD, Bitcoin

---

## Tijdsduur per run

Op een MacBook Air M1 met `qwen2.5:14b`:
- RSS ophalen + scrapen: ~3 min
- AI verwerking (17 artikelen): ~20-25 min
- Aandelen + PDF + email: ~2 min
- **Totaal: ~25-30 min**

De krant is klaar ruim voordat je opstaat (start om 07:00, klaar ~07:30).

---

## HA Add-on (alternatief)

De `nieuwsagent/` map bevat de originele Home Assistant Add-on versie. Zie de HA Add-on Store voor installatie via GitHub repository:
`https://github.com/mrmatena/nieuwsagent-addon`
