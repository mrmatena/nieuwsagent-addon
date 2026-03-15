# De NieuwsAgent

Een Home Assistant Add-on die dagelijks om **06:00** en **17:00** een gepersonaliseerde nieuwskrant genereert als PDF en deze per email verstuurt.

## Inhoud van de krant

- **80% Technologie** — Tweakers, The Verge, Engadget, MacRumors
- **10% Nationaal** — NOS, Nu.nl
- **10% Internationaal** — NOS Buitenland
- **Financieel** — S&P500, Nvidia, Apple, Microsoft, Google, Amazon, Meta, Tesla, Netflix, AMD, Bitcoin
- Alle artikelen **in het Nederlands** (automatisch vertaald via Qwen AI)
- Artikelen geselecteerd en samengevat door **Qwen2.5:3b** (lokaal, geen cloud)

---

## Vereisten

- Home Assistant OS of Home Assistant Supervised
- Toegang tot de Add-on Store
- Gmail account met 2-stapsverificatie

---

## Installatie — Stap voor stap

### Stap 1: Ollama Add-on installeren

Ollama draait het lokale AI-model (Qwen2.5:3b) voor samenvatten en vertalen.

1. Ga naar **Instellingen → Add-ons → Add-on Store**
2. Klik op de **drie puntjes** rechtsboven → **Repositories**
3. Voeg deze repository toe:
   ```
   https://github.com/alexbelgium/hassio-addons
   ```
4. Zoek naar **Ollama** en klik op **Installeren**
5. Start de Ollama add-on
6. Ga naar het tabblad **Terminal** van de Ollama add-on en voer uit:
   ```bash
   ollama pull qwen2.5:3b
   ```
   > Dit downloadt het model (~2GB). Dit duurt enkele minuten afhankelijk van je internetsnelheid.

7. Noteer de Ollama URL. Standaard is dit:
   ```
   http://homeassistant:11434
   ```

---

### Stap 2: Gmail App-wachtwoord aanmaken

> **Waarom?** Gmail vereist een apart "App-wachtwoord" voor applicaties die geen OAuth gebruiken. Je gewone wachtwoord werkt niet.

1. Ga naar [myaccount.google.com](https://myaccount.google.com)
2. Klik op **Beveiliging** in het linkermenu
3. Zorg dat **2-stapsverificatie** aanstaat (vereist voor App-wachtwoorden)
4. Zoek naar **App-wachtwoorden** (of ga direct naar: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords))
5. Klik op **App-wachtwoord maken**
6. Geef het een naam: bijv. `NieuwsAgent`
7. Kopieer het **16-karakter wachtwoord** (formaat: `xxxx xxxx xxxx xxxx`)

> Bewaar dit wachtwoord — je ziet het maar één keer!

---

### Stap 3: NieuwsAgent Add-on installeren

1. Ga naar **Instellingen → Add-ons → Add-on Store**
2. Klik op de **drie puntjes** → **Repositories**
3. Voeg de NieuwsAgent repository toe:
   ```
   https://github.com/JOUW_GITHUB_NAAM/nieuwsagent-ha-addon
   ```
   > Vervang `JOUW_GITHUB_NAAM` door je eigen GitHub gebruikersnaam nadat je deze repository hebt geforkt/gepubliceerd.
4. Zoek naar **NieuwsAgent** en klik op **Installeren**

---

### Stap 4: Add-on Configureren

1. Ga naar de geïnstalleerde **NieuwsAgent** add-on
2. Klik op het tabblad **Configuratie**
3. Vul de volgende velden in:

| Veld | Voorbeeld | Beschrijving |
|------|-----------|--------------|
| `gmail_address` | `jouw@gmail.com` | Je Gmail e-mailadres |
| `gmail_app_password` | `abcd efgh ijkl mnop` | Het app-wachtwoord uit Stap 2 |
| `ontvanger_email` | `jouw@gmail.com` | Ontvanger (mag hetzelfde zijn) |
| `ollama_url` | `http://homeassistant:11434` | URL van de Ollama add-on |
| `ollama_model` | `qwen2.5:3b` | Te gebruiken AI-model |
| `tijdstip_ochtend` | `06:00` | Tijdstip ochtendkrant (24u notatie) |
| `tijdstip_avond` | `17:00` | Tijdstip avondkrant (24u notatie) |

4. Klik op **Opslaan**

---

### Stap 5: Starten

1. Klik op **Starten** in de NieuwsAgent add-on
2. Ga naar het tabblad **Log** om de voortgang te volgen
3. Bij het opstarten wordt direct een **test-editie** gegenereerd en verstuurd
4. Controleer je inbox — de PDF zou binnen 15-20 minuten moeten aankomen

> **Let op:** De eerste run duurt langer omdat het AI-model de teksten één voor één verwerkt. Op een N100 processor is dit normaal (~10-15 minuten).

---

## Logs bekijken

Ga naar **Instellingen → Add-ons → NieuwsAgent → Log** voor real-time logging:

```
2026-03-15 06:00:01 [INFO] nieuwsagent: ═══ NieuwsAgent gestart — 15 maart 2026 Ochtend editie ═══
2026-03-15 06:00:01 [INFO] nieuwsagent: Stap 1/5: Nieuws ophalen van RSS-bronnen...
2026-03-15 06:01:23 [INFO] nieuwsagent: → 87 artikelen opgehaald
2026-03-15 06:01:23 [INFO] nieuwsagent: Stap 2/5: AI verwerking (scoren + samenvatten)...
2026-03-15 06:13:45 [INFO] nieuwsagent: → Geselecteerd: 9 tech, 4 nationaal, 4 internationaal
2026-03-15 06:13:46 [INFO] nieuwsagent: Stap 3/5: Aandelen ophalen...
2026-03-15 06:13:52 [INFO] nieuwsagent: Stap 4/5: PDF genereren...
2026-03-15 06:14:03 [INFO] nieuwsagent: Stap 5/5: Email versturen...
2026-03-15 06:14:05 [INFO] nieuwsagent: ═══ NieuwsAgent klaar — 15 maart 2026 Ochtend editie verstuurd ═══
```

---

## Problemen oplossen

### "Ollama niet bereikbaar"
- Controleer of de Ollama add-on draait
- Controleer de `ollama_url` in de configuratie
- Test met: `curl http://homeassistant:11434/api/tags`

### "Email versturen mislukt"
- Controleer of het app-wachtwoord correct is (geen spaties weglaten)
- Zorg dat 2-stapsverificatie aanstaat in je Google account
- Controleer of `gmail_address` een geldig Gmail adres is

### "Geen artikelen opgehaald"
- Controleer de internetverbinding van je HA server
- Mogelijk blokkeren RSS-bronnen tijdelijk — probeer later opnieuw

### "PDF generatie mislukt"
- Bekijk de volledige log voor foutmeldingen
- Controleer of er voldoende schijfruimte beschikbaar is

---

## Technische details

| Component | Technologie |
|-----------|-------------|
| AI-model | Qwen2.5:3b via Ollama |
| RSS-fetching | feedparser + requests |
| Artikel scraping | BeautifulSoup4 |
| PDF-generatie | WeasyPrint |
| Email | Gmail SMTP (STARTTLS) |
| Scheduling | APScheduler (Europe/Amsterdam) |
| Basisimage | Python 3.11-slim |

---

## Nieuwsbronnen

| Bron | Categorie | Taal in RSS |
|------|-----------|-------------|
| Tweakers.net | Technologie | Nederlands |
| The Verge | Technologie | Engels → NL |
| Engadget | Technologie | Engels → NL |
| MacRumors | Technologie | Engels → NL |
| NOS Algemeen | Nationaal | Nederlands |
| Nu.nl | Nationaal | Nederlands |
| NOS Buitenland | Internationaal | Nederlands |
