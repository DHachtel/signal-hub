# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Single private user: Daniel, a swing trader who researches US mid-cap growth /
volatile large-cap stocks alongside a non-trading day job. Not a public or
multi-tenant product — built, hosted, and used entirely for personal trading
research.

## Product Purpose

Daniel previously ran three disconnected daily research paths for finding
swing-trade candidates: an automated TechScreener Telegram bot, GainerAgent
(a separate day-trading gainer scanner), and manual insider-trade checks via
openinsider.com. None of them were actually used day to day — the data felt
stale or unreliable enough that he stopped checking. Signal Hub consolidates
the swing-trading-relevant sources (TechScreener's screening logic + insider
buying activity + a market regime indicator) into one dashboard with explicit
data-freshness flags, so what's shown can be trusted at a glance instead of
re-verified elsewhere. Success is Daniel actually opening and trusting it
regularly — not another report he learns to ignore.

## Positioning

The mechanism a disconnected set of tools couldn't offer: one validated view
combining technical swing-trading signals (Minervini Trend Template + EMA21
Pullback), insider purchase/cluster-buy activity, and SPY market-regime
status, each entry explicitly marked fresh or stale rather than silently
wrong. Zero-cost, zero-maintenance infrastructure (GitHub Actions, GitHub
Pages, JSONBin.io free tiers) — no server Daniel has to run, patch, or pay
for.

Confirmed long-term direction (not yet scoped or planned): Signal Hub is
meant to eventually fully replace TechScreener, including its chart analysis,
paper-trading simulator, trade journal, and backtest features — not stay
limited to a daily signal summary. GainerAgent's day-trading signals are
intended for a later integration as a second, explicitly distinct trading
style (day trading vs. swing trading, different timeframes) — deliberately
out of scope for the current version.

## Operating Context

- Checked via a browser dashboard on desktop and mobile; installable as a PWA
  on the phone home screen for app-like access.
- Data refreshes automatically 3x/day on trading days (10:00 / 13:30 / 16:45
  ET) via a GitHub Actions pipeline, or on demand via a "Refresh" button in
  the dashboard that triggers the same pipeline and polls for completion.
- A Telegram bot (reused from TechScreener's existing bot/chat) sends a
  short, link-only notification when something genuinely new appears (a new
  swing buy signal or a new insider cluster-buy) — a nudge to go look, not a
  full report repeated in the message.
- TechScreener's own automatic Telegram alerts are paused (schedule
  commented out, manual run still available) now that Signal Hub covers that
  ground; TechScreener's chart/simulator/journal/backtest UI remains
  available and unaffected until it's absorbed per the confirmed long-term
  direction above.
- Runs entirely on free-tier infrastructure — a hard constraint on every
  architectural choice, not a preference.

## Capabilities and Constraints

- No backend server: the dashboard is a single static HTML file (no build
  step, no framework) that reads one JSON document from JSONBin.io.
- The GitHub repository (`DHachtel/signal-hub`) must be public for GitHub
  Pages to be free, so no credentials are ever committed to source. JSONBin
  key, GitHub repo name, and a GitHub PAT (scoped to Actions read/write on
  this one repo only) are entered once by Daniel into a Settings panel and
  stored only in the browser's localStorage.
- Swing-scan logic (Minervini Trend Template, EMA21 Pullback, ~80-symbol
  universe) is ported from TechScreener's Python bot and must be kept in
  sync with it until TechScreener is fully retired.
- Insider-trading data is scraped directly from openinsider.com's public
  bulk-list pages (not routed through the separate "Hermes Agent" tool).
- Each symbol's data carries an explicit `fresh` / `stale` quality flag
  (≥252 daily bars required, data no older than 4 calendar days) — a stale
  or silently-wrong signal is treated as worse than showing no signal.
- Open / undecided: no scope or timeline yet for absorbing TechScreener's
  chart/simulator/journal/backtest capabilities into Signal Hub.
- Open / undecided: no scope or timeline yet for integrating GainerAgent's
  day-trading signals.

## Brand Commitments

Working name "Signal Hub," live at `https://dhachtel.github.io/signal-hub/`.
No other name, logo, or voice commitments exist yet.

## Evidence on Hand

No testimonials, case studies, or external users — single-user internal
tool. The live production dashboard itself is the only real evidence of
current state; it must never be dressed up with fabricated data, sample
users, or invented metrics, since every number it shows is meant to reflect
Daniel's actual trading signals.

## Product Principles

1. **Validity over completeness.** A signal must be verifiably correct (data
   freshness checked, logic tested against known-good fixtures), not merely
   plausible-looking. A stale or wrong signal is worse than no signal.
2. **Consolidation over proliferation.** New signal sources get folded into
   this one dashboard rather than spawning another separate report or tool.
3. **Zero-cost, zero-maintenance infrastructure.** Every architectural
   choice stays on free tiers and avoids anything Daniel has to run, patch,
   or pay for.
4. **Private by default.** Single-user tool; credentials and displayed data
   never leave Daniel's own browser and GitHub account, even though the
   repository itself is public for free hosting.
5. **Distinct trading styles stay distinct.** Swing trading (this tool) and
   day trading (GainerAgent) are different timeframes and different
   disciplines — planned integration keeps them clearly separated rather
   than blurring signals together.
