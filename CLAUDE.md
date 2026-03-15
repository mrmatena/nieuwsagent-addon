# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

NieuwsAgent is a **standalone macOS Python script** that generates a Dutch-language newspaper PDF twice daily (07:00 and 17:00) and emails it via Gmail SMTP. It uses a local `qwen2.5:14b` model via Ollama for AI scoring, summarisation, pull quotes and market commentary. Scheduling is handled by macOS **launchd**.

The `nieuwsagent/` subdirectory contains an older Home Assistant Add-on version (Dockerfile, `config.yaml`, `run.sh`) — the active codebase is under `src/`.

## Running

```bash
# One-off run (e.g. for testing)
python3 src/main.py Test

# Ochtend / Avond edition
python3 src/main.py Ochtend
python3 src/main.py Avond
```

**Test individual components:**
```bash
python3 -c "from src.fetcher import haal_alles_op; a = haal_alles_op(); print(len(a), 'artikelen'); print(set(x['bron'] for x in a))"
python3 -c "from src.stock_fetcher import haal_aandelen_op; [print(a['naam'], a['prijs'], a['afstand_hoog']) for a in haal_aandelen_op()]"
curl http://localhost:11434/api/tags
```

**Dependencies** (Python 3.14, Homebrew pango/cairo/gdk-pixbuf already installed):
```bash
pip3 install -r requirements.txt   # uses >= versions for Python 3.14 compat
```

## Configuration

`config.py` reads `config.json` in the project root (falls back to env vars):

```bash
cp config.json.example config.json   # then fill in credentials
```

Fields: `gmail_address`, `gmail_app_password`, `ontvanger_email`, `ollama_url`, `ollama_model`.

`config.json` is gitignored.

## Scheduling (launchd)

Two plist files in `launchd/` are the reference copies. Active plists installed at:

```
~/Library/LaunchAgents/nl.nieuwsagent.ochtend.plist   → runs 07:00
~/Library/LaunchAgents/nl.nieuwsagent.avond.plist     → runs 17:00
```

Logs: `~/Library/Logs/nieuwsagent-{ochtend,avond}.log`

```bash
launchctl unload ~/Library/LaunchAgents/nl.nieuwsagent.ochtend.plist
launchctl load   ~/Library/LaunchAgents/nl.nieuwsagent.ochtend.plist
```

## Architecture

`main.py` is **run-once** — no internal scheduler. Sequential pipeline:

```
fetcher.haal_alles_op()
  → ai_processor.verwerk_artikelen(artikelen, config)   # scores, tiers, summaries, pull quotes
    → stock_fetcher.haal_aandelen_op()
      → ai_processor.genereer_markt_commentaar(aandelen, config)
        → pdf_generator.genereer_pdf(template_data)     # PIL compression + WeasyPrint
          → emailer.stuur_email(pdf_bytes, config, editie, datum)
```

**Key design decisions:**
- **Error isolation:** Every external call (RSS, Ollama, yfinance, SMTP, WeasyPrint) is wrapped in try/except. Failures log and skip — the run never crashes entirely.
- **AI is optional:** Ollama timeouts fall back to the original RSS summary text (score defaults to 5.0 → tier "compact").
- **Temp files:** Scraped images → `/tmp/nieuwsagent_imgs/`. Compressed images → `/tmp/nieuwsagent_imgs/compressed/`. WeasyPrint HTML intermediate uses `tempfile.NamedTemporaryFile`, deleted after PDF generation.

## Score-Tier System

Every article gets an AI score (1–10) then a tier:

| Tier | Score | Layout | Summary length |
|------|-------|--------|----------------|
| hero | ≥ 9.0 | Full width, large foto | 250–300 woorden + pull-quote |
| feature | ≥ 7.0 | 49% width (2-col) | 120–150 woorden |
| compact | < 7.0 | 31% width (3-col) | 60–80 woorden |

Tiers are set in `ai_processor.bereken_tier()` and stored on each article dict as `artikel["tier"]`. `verwerk_artikelen()` assigns tiers before calling `genereer_samenvatting()`, which uses the tier to set the target word count.

## Module Responsibilities

| File | Purpose |
|------|---------|
| `src/config.py` | Loads `config.json` or env vars; applies defaults |
| `src/fetcher.py` | RSS fetch (feedparser) + article scrape (BeautifulSoup) + image download + deduplication |
| `src/ai_processor.py` | Ollama REST: scores articles, assigns tiers, generates Dutch summaries, pull quotes, market commentary |
| `src/stock_fetcher.py` | yfinance: S&P500 + 9 tech stocks + Bitcoin; 15s thread timeout; returns price, day%, 52w high/low |
| `src/pdf_generator.py` | PIL image compression per tier, Jinja2 render, WeasyPrint PDF conversion |
| `src/emailer.py` | Gmail SMTP over STARTTLS with PDF attachment |
| `src/templates/krant.html` | Wired-style magazine layout, Flexbox only (no CSS Grid) |

## RSS Sources (Dutch-only)

| Feed | Categorie |
|------|-----------|
| `https://feeds.tweakers.net/nieuws/top.rss` | tech |
| `https://www.bright.nl/feed/news.xml` | tech |
| `https://feeds.nos.nl/nosnieuwsalgemeen` | nationaal |
| `https://www.nu.nl/rss/Algemeen` | nationaal |
| `https://feeds.nos.nl/nosnieuwsbuitenland` | internationaal |

Selection: top 9 tech, top 4 nationaal, top 4 internationaal (sorted by Ollama score).

## Template Conventions

`krant.html` uses **Flexbox with explicit `width` percentages** — no `display: grid`, no CSS `gap` property (WeasyPrint doesn't support `gap` on flex containers; use `margin-right`/`margin-bottom` instead).

**Macros:** `render_hero(artikel)`, `render_feature(artikel)`, `render_compact(artikel)`, `foto(artikel, hoogte)`, `bron_badge(artikel)`, `samenvatting(artikel)`, `pijl(kleur)`, `format_tijd(iso_str)`

**Article dict shape** (all keys that the template uses):
```
titel, bron, categorie, gepubliceerd (ISO 8601 string), url
samenvatting (RSS fallback), samenvatting_nl (AI Dutch)
score (float), tier (hero|feature|compact)
afbeelding_pad (str|None), pull_quote (str, hero only)
```

**Template data keys** passed from `main.py`:
```
datum, editie, markt_commentaar
tech_artikelen, nationaal_artikelen, internationaal_artikelen
aandelen  →  naam, ticker, prijs, wijziging_pct, kleur, afstand_hoog
```

## Image Handling

1. **Scraping** (`fetcher.py`): article images downloaded to `/tmp/nieuwsagent_imgs/` during `haal_alles_op()`. Deduplicated by file path and URL — each image appears at most once across the edition.
2. **Compression** (`pdf_generator.py`): before Jinja2 render, `comprimeer_afbeelding()` resizes and JPEG-compresses per tier (hero: 800px/q70, feature: 600px/q70, compact: 180px/q65) → `/tmp/nieuwsagent_imgs/compressed/`.
3. **Template**: images referenced as `file://{{ artikel.afbeelding_pad }}`. Missing images show a dark placeholder block.

## WeasyPrint Compatibility Notes

- No `display: grid` — use `display: flex` with explicit widths
- No `gap` on flex containers — use `margin-right`/`margin-bottom` on children
- No `object-fit: cover` — use fixed-size containers with `overflow: hidden` carefully
- `page-break-before: always` works for forcing new pages (used before Markten section)
- `@page { size: A4; margin: 12mm 14mm; }` sets page dimensions
