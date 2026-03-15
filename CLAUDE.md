# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

NieuwsAgent is a **Home Assistant Add-on** that generates a Dutch-language newspaper PDF twice daily (06:00 and 17:00 Europe/Amsterdam) and emails it via Gmail SMTP. It uses a local Qwen2.5:3b model via Ollama for AI summarisation and translation.

## Running Locally

All modules live under `src/`. Run from the project root:

```bash
# Install dependencies
pip install -r requirements.txt

# Set required environment variables (HA reads /data/options.json in production)
export GMAIL_ADDRESS="jouw@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export ONTVANGER_EMAIL="jouw@gmail.com"
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="qwen2.5:3b"

# Run (triggers an immediate test edition on startup, then blocks on scheduler)
python src/main.py
```

**Test individual components:**
```bash
# Verify RSS feeds work
python -c "from src.fetcher import haal_alles_op; a = haal_alles_op(); print(len(a), 'artikelen')"

# Verify Ollama is reachable
curl http://localhost:11434/api/tags

# Verify stock fetcher
python -c "from src.stock_fetcher import haal_aandelen_op; print(haal_aandelen_op())"
```

**Build Docker image (HA Add-on):**
```bash
docker build -t nieuwsagent .
```

WeasyPrint requires system libraries (`libpango`, `libcairo`, etc.) — the Dockerfile installs them. Local runs need these installed on the host too.

## Architecture

The pipeline runs sequentially in `src/main.py::genereer_en_stuur(editie)`:

```
fetcher.haal_alles_op()
  → ai_processor.verwerk_artikelen(artikelen, config)
    → stock_fetcher.haal_aandelen_op()
      → pdf_generator.genereer_pdf(template_data)
        → emailer.stuur_email(pdf_bytes, config, editie, datum)
```

`scheduler.start_scheduler()` registers two APScheduler cron jobs and calls `genereer_en_stuur("Test")` immediately on startup before blocking.

**Key design decisions:**
- **Configuration:** In HA production, `config.py` reads `/data/options.json`. Locally it falls back to env vars. Never hardcode credentials.
- **Error isolation:** Every external call (RSS, Ollama, yfinance, SMTP, WeasyPrint) is wrapped in try/except. A failure in one step logs the error and returns early rather than crashing the scheduler.
- **AI is optional:** If Ollama is unreachable or times out, `ai_processor.py` falls back to the original RSS summary text. The run continues.
- **Temp files:** Scraped article images go to `/tmp/nieuwsagent_imgs/`. The HTML intermediate for WeasyPrint uses `tempfile.NamedTemporaryFile` and is deleted after PDF generation.

## Module Responsibilities

| File | Purpose |
|------|---------|
| `src/config.py` | Loads HA `options.json` or env vars; applies defaults |
| `src/fetcher.py` | RSS fetch (feedparser) + full article scrape (BeautifulSoup) + image download |
| `src/ai_processor.py` | Ollama REST client — scores articles 1-10, generates Dutch summaries |
| `src/stock_fetcher.py` | yfinance wrapper for S&P500 + 9 tech stocks + Bitcoin; 15s thread timeout per ticker |
| `src/pdf_generator.py` | Renders `krant.html` via Jinja2, converts to PDF bytes via WeasyPrint |
| `src/emailer.py` | Gmail SMTP over STARTTLS with PDF attachment |
| `src/scheduler.py` | APScheduler with Europe/Amsterdam timezone, time parsing with fallback to 06:00/17:00 |
| `src/templates/krant.html` | Jinja2 + Flexbox layout (no CSS Grid — WeasyPrint compatibility) |

## Template Conventions

`krant.html` uses **Flexbox throughout** — no `display: grid` (WeasyPrint has limited grid support). Macros are defined at the top of the template: `artikel_klein`, `artikel_compact`, `foto_groot`, `foto_klein`, `bron_rij`, `samenvatting`, `clip`, `pijl`.

The template expects `gepubliceerd` as an **ISO 8601 string** (`YYYY-MM-DDTHH:MM:SS`) — `fetcher.py` always converts datetime objects to this format before storing.

Article dicts passed to the template must include `samenvatting_nl` (AI-generated Dutch) with `samenvatting` as fallback. The `samenvatting()` macro handles this automatically.

## HA Add-on Configuration

Configurable fields in `config.yaml` (surfaced in HA UI):
- `gmail_address`, `gmail_app_password`, `ontvanger_email`
- `ollama_url` (default: `http://homeassistant:11434`), `ollama_model` (default: `qwen2.5:3b`)
- `tijdstip_ochtend` (default: `06:00`), `tijdstip_avond` (default: `17:00`) — 24h `HH:MM` format

## RSS Sources

7 feeds, categorised as `tech` / `nationaal` / `internationaal`. Selection: top 9 tech articles (score > threshold), top 4 nationaal, top 4 internationaal. Scores (1-10) assigned by Ollama.

English-language feeds (The Verge, Engadget, MacRumors) are translated to Dutch by the AI summarisation prompt.
