# Signal Hub — Design

**Datum:** 2026-07-24
**Status:** Genehmigt (Brainstorming abgeschlossen), bereit für Implementierungsplan

## Problem

Daniel nutzt aktuell vier getrennte Systeme zur Aktienrecherche:

- **TechScreener v23** — Swing-Screener (Minervini Trend Template + EMA21 Pullback), Telegram-Bot 3×/Tag via GitHub Actions → JSONBin
- **GainerAgent** — Pre-Market Gap-Scanner für Day-Trading (Warrior-Stil), eigener Telegram-Bot, Hetzner-Server
- **Hermes-Insider-Report** — Ad-hoc openinsider.com-Auswertung über den Discord-Assistenten
- **Diverse Cron-Reports** — Text-Push zu festen Uhrzeiten auf Telegram/Discord

Die Reports werden kaum genutzt, weil sie zum Lesezeitpunkt veraltet sind (Push statt Pull) und weil kein System eine Gesamtsicht pro Aktie bietet — ein Insider-Kauf und ein bestandenes Trend-Template für dasselbe Symbol tauchen nie zusammen auf.

## Entscheidung

**Ansatz A: GitHub Actions + JSONBin + GitHub Pages**, als neues eigenständiges Repo `signal-hub`. Kein Firebase (Blaze-Plan/Kreditkarte nötig für Scheduler, neues Ökosystem ohne Mehrwert für Single-User). Kein Hetzner-Server als Basis (Wartungsaufwand, koppelt Trading-Infra an Assistenz-Server) — bleibt als mögliche spätere Ausbaustufe für echte Live-Kurse, ist aber nicht Teil dieses Designs.

**Scope-Entscheidung:** Fokus ausschließlich auf **Swing-Trading**. Day-Trading (GainerAgent) wird **nicht** in den Hub integriert — GainerAgent läuft unverändert als eigenständiges Tool weiter, ist aber aus der Konsolidierung raus. Grund: kostenlose Datenquellen (Yahoo, ~15 Min Verzögerung) sind für Pre-Market-Gap-Momentum ungeeignet, für Swing aber völlig ausreichend.

**Datenschutz:** Scan-Ergebnisse bleiben privat über JSONBin (Schreibzugriff nur mit Master-Key aus GitHub Secret; Lesezugriff über einen Read-Key, der im Frontend eingebettet ist — das Bin ist nicht öffentlich auffindbar/indexiert).

## Architektur

```
GitHub Actions (Cron 3×/Tag, Zeiten wie bisheriger TechScreener-Bot + manueller workflow_dispatch)
  └─ signal_hub.py  (Pipeline, neues Repo)
       ├─ swing_scan()     → wiederverwendet check_trend_template()/detect_ema21_pullback()
       │                     aus TechScreener/github-alerts/screener.py (Logik kopiert, nicht importiert
       │                     — kein Cross-Repo-Dependency; Parity-Tests stellen Korrektheit sicher)
       ├─ insider_scan()   → neu: openinsider.com Scraping, gezielt für Swing-Universum + Cluster-Buy-
       │                     Zusatzliste außerhalb des Universums
       ├─ market_ampel()   → SPY-Trend (Logik aus screener.py übernommen)
       └─ validate()       → Datenqualitäts-Check vor Publish (siehe unten)
  └─ schreibt EIN JSON-Dokument nach JSONBin (privat, Master-Key als GitHub Secret)
  └─ bei neuen validen Signalen: kurze Telegram-Notification mit Link ins Dashboard
       (kein Report-Text mehr — nur Klingel + Link)

GitHub Pages (neue, schlanke Single-HTML-PWA "Signal Hub")
  └─ liest JSONBin (Read-Key im Frontend eingebettet)
  └─ Refresh-Button → GitHub Actions API (workflow_dispatch) → Re-Scan in ~2-3 Min,
     danach automatischer Reload
  └─ zeigt pro Symbol: Swing-Signal + Insider-Aktivität + Markt-Ampel nebeneinander
  └─ installierbar als PWA am Handy, kein Login nötig
```

**Warum ein gemeinsames JSON-Dokument statt getrennter Listen:** Nur so kann das Dashboard eine Sicht "pro Aktie" bauen — Swing-Setup und Insider-Aktivität gleichzeitig sichtbar, statt wie heute in getrennten Kanälen.

## Konsolidierung — was sich ändert

- **Hermes-Insider-Report** entfällt als Ad-hoc-Discord-Feature; die Logik wandert (neu implementiert, da kein bestehender Code dafür existiert) in `insider_scan()`. Hermes bleibt allgemeiner Assistent, macht aber keine Daten-Reports mehr.
- **Feste Telegram-Text-Reports** (TechScreener-Bot) werden durch kurze Notifications mit Link ersetzt — nur wenn es tatsächlich neue/veränderte Signale gibt.
- **GainerAgent** bleibt unverändert und außerhalb des Hubs (siehe Scope-Entscheidung oben).
- **TechScreener v23-App** bleibt bestehen als Analyse-Werkzeug (Chart, Journal, Backtest, Simulator) — der Signal Hub wird der tägliche Einstiegspunkt für die Frage "wo schauen?", TechScreener bleibt Werkzeug für die Tiefenanalyse eines gefundenen Kandidaten.

## Datenqualität ("muss valide sein")

Dies ist eine explizite Design-Anforderung, kein Nebenaspekt:

1. **Validierungsschritt vor Publish** (`validate()`): prüft pro Symbol Mindestkriterien — ≥252 Handelstage für Trend Template vorhanden, Kursdaten nicht älter als ein definierter Schwellwert, keine NaN/None in Kernfeldern. Scheitert die Prüfung, wird das Symbol als `data_quality: "stale"` mit Begründung markiert statt mit potenziell falschen Werten angezeigt.
2. **Lauf-Status sichtbar**: Jedes JSONBin-Dokument enthält `meta.generated_at`, `meta.run_status` (`ok`/`partial`/`failed`) und pro Quelle (`swing_scan`, `insider_scan`, `market_ampel`) einen eigenen Status + Timestamp. Das Dashboard zeigt das prominent als Freshness-Banner — sofort erkennbar, ob gerade veraltete Daten angezeigt werden.
3. **Insider-Daten-Validierung**: Filing-Datum und Transaktionsdatum werden getrennt erfasst (openinsider-Filings können verzögert/nachkorrigiert sein). Form-4-Verkäufe werden gefiltert (nicht signalrelevant). Mindestschwelle $50.000 Trade-Wert, um Rauschen aus Routine-Trades rauszuhalten.
4. **Parity-Absicherung**: Der bestehende `tests/parity_check.py`/`.js`-Mechanismus aus TechScreener wird für die im Hub wiederverwendeten Funktionen (Trend Template, EMA Pullback) in `signal-hub` übernommen, damit die Swing-Logik nachweislich korrekt bleibt statt sich unbemerkt zu verschieben.

## Datenmodell (JSONBin-Dokument)

```json
{
  "meta": {
    "generated_at": "2026-07-24T14:32:00Z",
    "run_status": "ok",
    "sources": {
      "swing_scan": {"status": "ok", "ts": "2026-07-24T14:30:00Z"},
      "insider_scan": {"status": "ok", "ts": "2026-07-24T14:31:00Z"},
      "market_ampel": {"status": "ok", "ts": "2026-07-24T14:30:00Z"}
    }
  },
  "market": { "spy_trend": "above_ema20", "note": "..." },
  "symbols": {
    "CAVA": {
      "price": 123.4,
      "swing": {
        "template_pass": true,
        "signal": "buy",
        "entry": 120.1, "stop": 112.0, "trail": 118.5,
        "criteria": [true, true, true, true, true, true]
      },
      "insider": {
        "cluster_buy": true,
        "trades": [
          {"insider": "...", "role": "CEO", "value": 120000, "transacted": "2026-07-20", "filed": "2026-07-22"}
        ]
      },
      "data_quality": "fresh"
    },
    "XYZ": { "data_quality": "stale", "reason": "Kursdaten >24h alt" }
  }
}
```

Symbole landen in `symbols`, wenn sie im TechScreener-Swing-Universum (~80 Symbole) sind **oder** auf der Insider-Cluster-Buy-Trefferliste auftauchen. Kein vollständiger Markt-Scan für Insider-Trades — gezielt fürs Universum plus Zusatzliste, damit keine neuen Kandidaten außerhalb des bekannten Universums übersehen werden.

## Dashboard (Single-HTML-PWA)

- **Eine sortierbare Tabelle**: Symbol · Preis · Swing-Signal (Template/Pullback) · Insider-Badge (🟢 Cluster-Buy / —) · Markt-Ampel-Kontext
- **Detail-Panel** bei Klick auf ein Symbol: Kriterien-Breakdown (welche der 6 Trend-Template-Kriterien erfüllt) + Insider-Trade-Liste
- **Refresh-Button**: löst `workflow_dispatch` über die GitHub-API aus, zeigt Wartezustand, lädt nach Abschluss automatisch neu
- **Freshness-Banner**: "Zuletzt aktualisiert vor X Min", Warnfarbe wenn `run_status != ok` oder Daten über Schwellwert alt
- Kein Login nötig, als PWA am Handy installierbar

## Offene Punkte für den Implementierungsplan

- Genauer Schwellwert für "Kursdaten zu alt" (Vorschlag: 24h)
- Cron-Zeiten (an bestehende TechScreener-Bot-Zeiten anlehnen oder eigene wählen?)
- GitHub-Token-Scope für den `workflow_dispatch`-Trigger aus dem Frontend (Personal Access Token mit minimalem Scope, im Frontend eingebettet oder über einen Proxy?)
- Ob `insider_scan()` als eigenständiges Python-Modul mit eigenen Tests entsteht oder direkt in `signal_hub.py` integriert wird

## Nicht Teil dieses Designs

- Live-Kurse in Echtzeit (Hetzner-Ausbaustufe, spätere Entscheidung)
- Integration von GainerAgent (Day-Trading, bewusst ausgeschlossen)
- Migration von TechScreener-Journal/Watchlist in den Hub (möglich, aber nicht jetzt)
