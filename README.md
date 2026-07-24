# Signal Hub

Konsolidierter Swing-Trading-Signal-Hub: Minervini Trend Template + EMA21 Pullback
(portiert aus TechScreener), Insider-Trading-Aktivitaet (openinsider.com) und
Markt-Ampel (SPY vs. 50-Tage-SMA) in einem taeglich per Knopfdruck aktualisierbaren
Dashboard. Kostenlos: GitHub Actions + JSONBin.io + GitHub Pages.

Dashboard: https://dhachtel.github.io/signal-hub/

Konzept: `docs/superpowers/specs/2026-07-24-signal-hub-design.md`
Implementierungsplan: `docs/superpowers/plans/2026-07-24-signal-hub.md`

## Setup

### 1. JSONBin.io Bin anlegen

1. Account auf [jsonbin.io](https://jsonbin.io) anlegen (kostenlos).
2. Neuen Bin erstellen mit initialem Inhalt `{}`.
3. Bin-ID (aus der URL) und Master-Key (aus dem Account-Dashboard) notieren.

### 2. Telegram-Bot (optional, fuer Benachrichtigungen)

1. Bot bei [@BotFather](https://t.me/BotFather) anlegen, Token notieren.
2. Chat-ID ermitteln (z.B. ueber `@userinfobot` in Telegram).

### 3. GitHub Secrets setzen

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Wert |
|---|---|
| `JSONBIN_MASTER_KEY` | Master-Key aus Schritt 1 |
| `JSONBIN_BIN_ID` | Bin-ID aus Schritt 1 |
| `TELEGRAM_BOT_TOKEN` | Token aus Schritt 2 (optional) |
| `TELEGRAM_CHAT_ID` | Chat-ID aus Schritt 2 (optional) |

### 4. GitHub Pages

Bereits aktiv: Settings → Pages → Source "Deploy from a branch", Branch `main`, Folder `/ (root)`.
Dashboard: https://dhachtel.github.io/signal-hub/

### 5. Fine-grained Personal Access Token fuer den Refresh-Button

Der Refresh-Button im Dashboard loest per Browser-Request einen `workflow_dispatch`
aus. Dafuer wird ein **fine-grained PAT** benoetigt, **beschraenkt auf dieses eine
Repo**, mit **ausschliesslich** der Permission "Actions: Read and write" (keine
Contents/Code-Rechte!).

1. [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta) → Generate new token.
2. Repository access: "Only select repositories" → `signal-hub`.
3. Permissions: "Actions" → "Read and write". Alles andere auf "No access" lassen.
4. Ablaufdatum setzen (z.B. 90 Tage) — Erinnerung, den Token danach zu rotieren.
5. Token kopieren (wird nur einmal angezeigt).

**Wichtig:** Dieser Token wird NICHT in den Quellcode eingetragen, sondern erst im
Dashboard selbst unter ⚙ Einstellungen eingegeben (landet dann nur in
`localStorage` des Browsers, niemals in Git).

### 6. Dashboard konfigurieren

1. https://dhachtel.github.io/signal-hub/ oeffnen.
2. ⚙ Einstellungen: JSONBin Bin ID, JSONBin Master Key, GitHub Repo
   (`DHachtel/signal-hub`), GitHub PAT aus Schritt 5 eintragen. Speichern.
3. "Refresh" klicken, um den ersten Scan manuell auszuloesen (~2-3 Min), oder
   auf den naechsten Cron-Lauf warten (10:00 / 13:30 / 16:45 ET, Mo-Fr).

## Lokal entwickeln

```bash
python -m venv venv
source venv/bin/activate  # oder venv\Scripts\activate unter Windows
pip install -r requirements-dev.txt
pytest tests/ -v
python main.py  # benoetigt die Env-Vars aus Schritt 3 lokal gesetzt
```

## Architektur

Siehe `docs/superpowers/specs/2026-07-24-signal-hub-design.md` fuer die
vollstaendige Architektur-Entscheidung (Ansatz, Datenmodell, Datenqualitaet).

Kurzueberblick:

```
pipeline/
  indicators.py      EMA/SMA/ATR/RS (portiert aus TechScreener)
  swing_scan.py       Trend Template + EMA21 Pullback + Universum
  insider_scan.py     openinsider.com Bulk-Scan (Universum + Cluster-Buys)
  market_ampel.py     SPY-Regime (bull/bear via 50-SMA)
  validate.py          Datenqualitaets-Gate (fresh/stale)
  jsonbin_client.py    JSONBin.io read/write
  telegram_notify.py   Link-only Benachrichtigung
  build.py              Orchestrierung + Diff-basierte Notifications
main.py                Entry Point fuer GitHub Actions
index.html              PWA-Dashboard (kein Build-Step, vanilla JS)
```
