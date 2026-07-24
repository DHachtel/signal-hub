# Chart View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an inline candlestick chart (3 months, EMA21 overlay) to Signal Hub's dashboard table — clicking a symbol row expands a live-fetched chart directly beneath it, so the numbers in the table (Template pass/fail, Signal buy) become visually verifiable without leaving the page.

**Architecture:** Pure addition to the existing single-file `index.html` (no build step, no framework, matches the project's established convention). The chart fetches its own OHLCV data client-side per symbol on click — it is deliberately independent of the JSONBin document and the GitHub Actions pipeline, since baking 3 months of candles for ~80 symbols into the daily-scan JSON would blow past JSONBin's free-tier size limit and go stale between refreshes anyway. Data fetching and canvas rendering are ported from `TechScreener_Pro_v23.html`'s `fetchWithProxy`/`fetchYahooOHLCV`/`calcEMA`/`drawChart`, stripped down to only what the confirmed brief needs (candles + EMA21, fixed 3-month range, no volume/MACD/Bollinger Bands/pattern overlays/zoom).

**Tech Stack:** Vanilla JS, HTML5 Canvas, no new dependencies. Reuses the existing dark-theme CSS custom properties already defined in `index.html`'s `:root`.

**Reference brief:** confirmed via `/impeccable shape` this session (see conversation) — no separate spec file; this plan is the executable form of that brief.

---

## Implementation Notes (decisions made while planning)

1. **No JS test framework exists in this project** (single HTML file, no `package.json`, no build step) — matching the precedent already set by Tasks 13–15 of `docs/superpowers/plans/2026-07-24-signal-hub.md`, verification here is manual: serve the directory locally (`python -m http.server 8000`) and check behavior in a real browser, using the browser tool's console/screenshot capabilities where available. This is a deliberate, previously-reviewed convention for this project, not a shortcut.
2. **Canvas can't read CSS custom properties directly.** `drawMiniChart`'s colors are hardcoded hex values copied verbatim from `index.html`'s `:root` block (`--green: #3ecf8e`, `--red: #ef5b5b`, `--amber: #e0a52c`, `--border: #2a2f3a`, `--bg: #0f1115`, `--muted: #8b93a3`). If the theme palette ever changes, these must be updated too — noted here so it isn't a silent trap for future work.
3. **One chart open at a time**, enforced via a module-level `openChartSym` variable. `renderTable()` must reset `openChartSym = null` on every re-render (e.g. after a Refresh), otherwise clicking the same symbol that was open before a refresh would silently no-op instead of reopening — this is fixed as part of Task 2, not left as a latent bug.
4. **Chart does not respect a symbol's `data_quality: 'stale'` flag** from the JSONBin document — the chart always does its own fresh, live fetch, so a "stale" swing-scan flag (which only means the *pipeline's* 252-bar/4-day freshness check failed) has no bearing on whether a live chart can render. This was confirmed as intentional in the brief.
5. **No live-resize handling.** The chart canvas is sized once when the panel opens; if the user resizes the browser window while a chart is open, it won't re-scale until they collapse and reopen it. This is an accepted YAGNI simplification for a short-lived expand/collapse UI, not an oversight.

---

## Task 1: Chart Data Layer

Adds the CORS-proxy fetch chain, the Yahoo Finance OHLCV fetch, and a JS EMA calculation — ported from TechScreener, scoped to a fixed 3-month range and no fields beyond what the chart needs.

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Insert the chart data-layer functions**

In `index.html`, find this exact transition between `renderTable()` and `loadAndRender()`:

```javascript
    tbody.appendChild(tr);
  }
}

async function loadAndRender() {
```

Replace it with:

```javascript
    tbody.appendChild(tr);
  }
}

// ═══════════════════════════════════════════
// CHART PANEL (candlesticks + EMA21, live-fetched per symbol)
// Ported from TechScreener_Pro_v23.html's fetchWithProxy/fetchYahooOHLCV/
// calcEMA, scoped to a fixed 3-month range with EMA21 only.
// ═══════════════════════════════════════════

const CHART_PROXIES = [
  'https://corsproxy.io/?',
  'https://api.allorigins.win/raw?url=',
  'https://thingproxy.freeboard.io/fetch/',
  'https://api.codetabs.com/v1/proxy?quest='
];

async function fetchWithCorsProxy(url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(4000) });
    if (r.ok) return await r.json();
  } catch (e) {
    // direct fetch failed (likely CORS) — fall through to proxies
  }
  for (const proxy of CHART_PROXIES) {
    try {
      const r = await fetch(proxy + encodeURIComponent(url), { signal: AbortSignal.timeout(5000) });
      if (r.ok) {
        const text = await r.text();
        return JSON.parse(text);
      }
    } catch (e) {
      // try next proxy
    }
  }
  return null;
}

function calcEmaJs(arr, period) {
  const k = 2 / (period + 1);
  const result = new Array(arr.length).fill(null);
  if (arr.length < period) return result;
  const seedEnd = period - 1;
  let sum = 0;
  for (let i = 0; i < period; i++) sum += (arr[i] || 0);
  result[seedEnd] = sum / period;
  for (let i = seedEnd + 1; i < arr.length; i++) {
    result[i] = (arr[i] || 0) * k + result[i - 1] * (1 - k);
  }
  return result;
}

async function fetchChartOHLCV(sym) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${sym}?interval=1d&range=3mo`;
  const raw = await fetchWithCorsProxy(url);
  const result = raw && raw.chart && raw.chart.result && raw.chart.result[0];
  if (!result || !result.timestamp || !result.indicators || !result.indicators.quote) return null;
  const ts = result.timestamp;
  const quote = result.indicators.quote[0];
  const candles = [];
  for (let i = 0; i < ts.length; i++) {
    if (quote.close[i] == null || quote.high[i] == null || quote.low[i] == null || quote.low[i] <= 0) continue;
    candles.push({
      t: ts[i] * 1000,
      o: quote.open[i] != null ? quote.open[i] : quote.close[i],
      h: quote.high[i],
      l: quote.low[i],
      c: quote.close[i],
    });
  }
  if (candles.length < 20) return null;
  const closes = candles.map(c => c.c);
  const ema21 = calcEmaJs(closes, 21);
  candles.forEach((c, i) => { c.ema21 = ema21[i]; });
  return candles;
}

async function loadAndRender() {
```

- [ ] **Step 2: Verify manually in the browser console**

Serve the directory locally:

```bash
cd "C:\Users\Daniel Hachtel\Documents\AI Workspace\Projekte\signal-hub"
python -m http.server 8000
```

Open `http://localhost:8000/index.html` in a browser, open DevTools console, and run:

```javascript
await fetchChartOHLCV('AAPL')
```

Expected: an array of ≥20 objects, each with `t`, `o`, `h`, `l`, `c`, `ema21` keys. `ema21` is `null` for the first ~20 entries and a number thereafter (EMA needs 21 bars to seed).

Also verify the "insufficient data" path:

```javascript
await fetchChartOHLCV('THISISNOTATICKER')
```

Expected: `null`.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\Daniel Hachtel\Documents\AI Workspace\Projekte\signal-hub"
git add index.html
git commit -m "feat: add chart data layer (CORS proxy fetch + EMA21)"
```

---

## Task 2: Row Click Toggle (expand/collapse, one at a time)

Wires table rows to open/close an inline panel beneath them, fetching real data but not yet drawing a chart (that's Task 3) — this task's own scope is verified by confirming the fetch + toggle + single-open-panel mechanics work correctly on their own.

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add chart panel CSS**

In `index.html`'s `<style>` block, find:

```css
  #empty-state { padding: 40px; text-align: center; color: var(--muted); }
```

Replace it with:

```css
  #empty-state { padding: 40px; text-align: center; color: var(--muted); }
  tr[data-sym] { cursor: pointer; }
  .chart-row td { padding: 0; border-bottom: 1px solid var(--border); }
  .chart-panel { padding: 16px; background: var(--bg); }
  .chart-panel .chart-title { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
  .chart-panel canvas { width: 100%; height: 220px; display: block; }
  .chart-panel .chart-status { padding: 24px 0; text-align: center; color: var(--muted); font-size: 13px; }
  .chart-panel .chart-status.error { color: var(--red); }
  .chart-panel .chart-retry { margin-top: 8px; }
  @media (max-width: 600px) {
    .chart-panel canvas { height: 160px; }
  }
```

- [ ] **Step 2: Tag each row with its symbol and reset open-chart state on re-render**

Find this line inside `renderTable()`:

```javascript
  tbody.innerHTML = '';
```

Replace it with:

```javascript
  tbody.innerHTML = '';
  openChartSym = null;
```

Find this line (inside the `for (const [sym, data] of rows)` loop):

```javascript
    const tr = document.createElement('tr');
```

Replace it with:

```javascript
    const tr = document.createElement('tr');
    tr.dataset.sym = sym;
```

- [ ] **Step 3: Add the toggle logic**

Find the `fetchChartOHLCV` function you added in Task 1 (it ends with `return candles; }`). Immediately after its closing brace, insert:

```javascript

let openChartSym = null;

function closeOpenChartRow() {
  const existing = document.querySelector('tr.chart-row');
  if (existing) existing.remove();
  openChartSym = null;
}

async function toggleChartRow(sym, rowEl) {
  if (openChartSym === sym) {
    closeOpenChartRow();
    return;
  }
  closeOpenChartRow();
  openChartSym = sym;

  const chartRow = document.createElement('tr');
  chartRow.className = 'chart-row';
  chartRow.dataset.sym = sym;
  const td = document.createElement('td');
  td.colSpan = 6;
  td.innerHTML = `
    <div class="chart-panel">
      <div class="chart-title">${escapeHtml(sym)} — 3 Monate, EMA21</div>
      <div class="chart-status">Lade Chart...</div>
    </div>
  `;
  chartRow.appendChild(td);
  rowEl.after(chartRow);

  const panel = td.querySelector('.chart-panel');
  const status = panel.querySelector('.chart-status');

  try {
    const candles = await fetchChartOHLCV(sym);
    if (openChartSym !== sym) return; // user closed/switched while this fetch was in flight
    if (!candles) {
      status.textContent = 'Keine ausreichenden Kursdaten verfuegbar.';
      status.className = 'chart-status error';
      return;
    }
    status.remove();
    const debugEl = document.createElement('div');
    debugEl.style.cssText = 'font-family:monospace;font-size:11px;color:var(--muted)';
    debugEl.textContent = `${candles.length} Kerzen geladen. Letzter Kurs: $${candles[candles.length - 1].c.toFixed(2)}`;
    panel.appendChild(debugEl);
  } catch (e) {
    if (openChartSym !== sym) return;
    status.textContent = `Fehler beim Laden: ${e.message}`;
    status.className = 'chart-status error';
  }
}

document.getElementById('table-body').addEventListener('click', (e) => {
  const tr = e.target.closest('tr[data-sym]');
  if (!tr || tr.classList.contains('chart-row')) return;
  toggleChartRow(tr.dataset.sym, tr);
});
```

The `tr.classList.contains('chart-row')` check matters: the injected chart-row also carries a `data-sym` attribute (so it matches `tr[data-sym]` too), and without this check, clicking anywhere inside the open chart panel — the loading text, the debug line, empty panel space — would immediately collapse it again, since the delegated handler would treat that click as toggling the chart-row's own symbol.

(The `debugEl` block is a temporary placeholder — Task 3 replaces it with the real canvas chart. Leaving it here lets this task verify the fetch/toggle mechanics on their own before rendering is added.)

- [ ] **Step 4: Verify manually in the browser**

With the local server from Task 1 still running, open `http://localhost:8000/index.html`, configure Settings with real JSONBin credentials (or use whatever was already configured from earlier signal-hub setup), and:

1. Click a symbol row. Expected: a row appears beneath it showing "Lade Chart..." then "`N` Kerzen geladen. Letzter Kurs: `$X.XX`".
2. Click the same row again. Expected: the chart row collapses (removed).
3. Click a different symbol row while one is already open. Expected: the previous chart row disappears and a new one opens for the newly clicked symbol — never two open at once.
4. Click "Refresh" (or reload the page) while a chart row is open, wait for the table to re-render, then click the *same* symbol that was open before. Expected: it opens again (confirms the `openChartSym = null` reset in Step 2 works — without it, this would incorrectly no-op).

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Daniel Hachtel\Documents\AI Workspace\Projekte\signal-hub"
git add index.html
git commit -m "feat: add inline chart row toggle (expand/collapse, one at a time)"
```

---

## Task 3: Canvas Rendering (candlesticks + EMA21)

Replaces Task 2's debug placeholder with the real chart: candlesticks colored by up/down close, an EMA21 overlay line, and a right-side price axis — matching the dark theme already established in `index.html`.

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Replace the debug placeholder with real canvas rendering**

Find this block inside `toggleChartRow` (added in Task 2):

```javascript
    status.remove();
    const debugEl = document.createElement('div');
    debugEl.style.cssText = 'font-family:monospace;font-size:11px;color:var(--muted)';
    debugEl.textContent = `${candles.length} Kerzen geladen. Letzter Kurs: $${candles[candles.length - 1].c.toFixed(2)}`;
    panel.appendChild(debugEl);
```

Replace it with:

```javascript
    status.remove();
    const canvas = document.createElement('canvas');
    panel.appendChild(canvas);
    drawMiniChart(canvas, candles);
```

- [ ] **Step 2: Add the `drawMiniChart` function**

Immediately after the `toggleChartRow` function's closing brace (before the `document.getElementById('table-body').addEventListener(...)` line you added in Task 2), insert:

```javascript

function drawMiniChart(canvas, candles) {
  const width = canvas.parentElement.clientWidth;
  const height = 220;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  canvas.style.width = width + 'px';
  canvas.style.height = height + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const padT = 12, padB = 12, padL = 4, padR = 54;
  const left = padL, right = width - padR, top = padT, bottom = height - padB;
  const n = candles.length;
  const colW = (right - left) / n;
  const bodyW = Math.max(1, colW * 0.6);

  ctx.fillStyle = '#0f1115'; // matches --bg
  ctx.fillRect(0, 0, width, height);

  let minP = Infinity, maxP = -Infinity;
  candles.forEach(c => {
    if (c.h > maxP) maxP = c.h;
    if (c.l < minP) minP = c.l;
    if (c.ema21 != null) {
      if (c.ema21 > maxP) maxP = c.ema21;
      if (c.ema21 < minP) minP = c.ema21;
    }
  });
  const priceRange = (maxP - minP) || 1;
  const py = p => top + (maxP - p) / priceRange * (bottom - top);
  const px = i => left + (i + 0.5) * colW;

  ctx.strokeStyle = '#2a2f3a'; // matches --border
  ctx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {
    const y = top + (bottom - top) * i / 3;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
  }

  ctx.strokeStyle = '#e0a52c'; // matches --amber
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  let started = false;
  candles.forEach((c, i) => {
    if (c.ema21 == null) return;
    const x = px(i), y = py(c.ema21);
    if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
  });
  ctx.stroke();

  candles.forEach((c, i) => {
    const x = px(i);
    const up = c.c >= c.o;
    const color = up ? '#3ecf8e' : '#ef5b5b'; // matches --green / --red
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, py(c.h));
    ctx.lineTo(x, py(c.l));
    ctx.stroke();
    const bodyTop = py(Math.max(c.o, c.c));
    const bodyBottom = py(Math.min(c.o, c.c));
    ctx.fillRect(x - bodyW / 2, bodyTop, bodyW, Math.max(1, bodyBottom - bodyTop));
  });

  ctx.fillStyle = '#8b93a3'; // matches --muted
  ctx.font = '10px monospace';
  ctx.textAlign = 'left';
  for (let i = 0; i <= 3; i++) {
    const priceVal = maxP - priceRange * i / 3;
    const y = top + (bottom - top) * i / 3;
    ctx.fillText('$' + priceVal.toFixed(2), right + 4, y + 3);
  }
}
```

- [ ] **Step 3: Verify manually in the browser**

Reload `http://localhost:8000/index.html`, click a symbol row with sufficient data. Expected:

- A candlestick chart renders: green candles for up days, red for down days.
- An amber EMA21 line runs through the candles (flat/absent for the first ~20 bars, present after).
- Price labels with `$` values appear along the right edge.
- The chart visually fills the row's width and is ~220px tall.

If a browser screenshot tool is available, capture the expanded row and visually confirm the candles are legible (not overlapping/illegibly thin) and colors match the dark theme (dark background, no white flashes).

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\Daniel Hachtel\Documents\AI Workspace\Projekte\signal-hub"
git add index.html
git commit -m "feat: render candlesticks + EMA21 on canvas"
```

---

## Task 4: Error State + Retry

Adds a retry affordance to both failure paths already stubbed in Task 2 (insufficient data, and fetch/network errors) so a transient failure (proxy timeout, temporary rate limit) doesn't require re-clicking the row twice (collapse then reopen).

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add retry buttons to both error branches**

Find this block inside `toggleChartRow` (the "insufficient data" branch):

```javascript
    if (!candles) {
      status.textContent = 'Keine ausreichenden Kursdaten verfuegbar.';
      status.className = 'chart-status error';
      return;
    }
```

Replace it with:

```javascript
    if (!candles) {
      status.innerHTML = 'Keine ausreichenden Kursdaten verfuegbar.<br><button class="chart-retry">Erneut versuchen</button>';
      status.className = 'chart-status error';
      status.querySelector('.chart-retry').addEventListener('click', () => {
        closeOpenChartRow();
        toggleChartRow(sym, rowEl);
      });
      return;
    }
```

Find the catch block right below it:

```javascript
  } catch (e) {
    if (openChartSym !== sym) return;
    status.textContent = `Fehler beim Laden: ${e.message}`;
    status.className = 'chart-status error';
  }
```

Replace it with:

```javascript
  } catch (e) {
    if (openChartSym !== sym) return;
    status.innerHTML = `Fehler beim Laden: ${escapeHtml(e.message)}<br><button class="chart-retry">Erneut versuchen</button>`;
    status.className = 'chart-status error';
    status.querySelector('.chart-retry').addEventListener('click', () => {
      closeOpenChartRow();
      toggleChartRow(sym, rowEl);
    });
  }
```

- [ ] **Step 2: Verify manually in the browser**

With the local server running, open DevTools → Network tab → set throttling to "Offline". Click a symbol row.

Expected: after the fetch attempts exhaust (direct fetch + all 4 proxies fail), the panel shows "Fehler beim Laden: ..." with a red "Erneut versuchen" button.

Set Network throttling back to "No throttling" (or "Online"), click "Erneut versuchen".

Expected: the panel re-fetches and renders the real chart (confirms retry re-triggers `toggleChartRow` correctly via close+reopen).

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\Daniel Hachtel\Documents\AI Workspace\Projekte\signal-hub"
git add index.html
git commit -m "feat: add retry button to chart error states"
```

---

## Task 5: Final Verification

No new files — confirms the whole feature works end to end, on both desktop and mobile viewport sizes, without breaking any existing dashboard functionality.

- [ ] **Step 1: Full desktop pass**

With the local server running and Settings configured with real credentials, open `http://localhost:8000/index.html`:

- Click through 3–4 different symbol rows one at a time; confirm each renders correctly and only one is ever open.
- Confirm existing functionality is unaffected: sorting headers still clickable, "Refresh" button still works and re-fetches the JSONBin document, "Einstellungen" modal still opens/saves/closes correctly.
- Confirm the empty-state message (`Keine Daten...`) still shows correctly when settings are cleared.

- [ ] **Step 2: Mobile viewport pass**

Resize the browser window (or use DevTools device toolbar) to a narrow width (~375px). Click a symbol row.

Expected: the chart panel and canvas scale down to fit (per the `@media (max-width: 600px)` rule from Task 2), no horizontal overflow/scrollbar introduced on the page.

- [ ] **Step 3: Check for design-hook findings**

If this project has the Impeccable design hook active (it fired earlier this session on `index.html` edits), address any findings it surfaces on this change the same way as before this session: fix real issues, or explicitly note why a finding doesn't apply, before considering this task done.

- [ ] **Step 4: Final commit** (only if Steps 1–3 required fixes; otherwise this task produces no diff)

```bash
cd "C:\Users\Daniel Hachtel\Documents\AI Workspace\Projekte\signal-hub"
git add -A
git commit -m "fix: address issues found during chart view final verification"
git push
```

If no fixes were needed, just push the accumulated commits from Tasks 1–4:

```bash
cd "C:\Users\Daniel Hachtel\Documents\AI Workspace\Projekte\signal-hub"
git push
```

---

## Self-Review Notes

- **Brief coverage:** row click → inline expand (Task 2), 3-month fixed range (Task 1's `range=3mo`), price + EMA21 only, no other overlays (Task 3), one chart open at a time (Task 2), independent live fetch per symbol regardless of `data_quality` (Task 1, confirmed in Implementation Notes), loading/error/retry states (Tasks 2 and 4), mobile responsiveness (Task 5), existing table/refresh/settings untouched (verified in Task 5).
- **Type/name consistency check:** `fetchChartOHLCV`, `calcEmaJs`, `toggleChartRow`, `closeOpenChartRow`, `drawMiniChart`, and `openChartSym` are each defined once (Tasks 1–3) and referenced identically everywhere they're used later (Tasks 2–5) — no renaming drift.
- **Deviation flagged explicitly:** Task 2 intentionally ships a temporary debug placeholder (removed in Task 3) so the toggle/fetch mechanics are verifiable independent of rendering — this is standard incremental-build practice for this project (the same pattern was used across Tasks 13–15 of the original signal-hub plan), not a stray TODO.
