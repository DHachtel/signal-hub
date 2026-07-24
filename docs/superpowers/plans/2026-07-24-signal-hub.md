# Signal Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `signal-hub` — a free GitHub Actions + JSONBin + GitHub Pages pipeline and PWA dashboard that consolidates swing-trading signals (Minervini Trend Template + EMA21 Pullback, ported from TechScreener) with insider-trading activity (openinsider.com) and a market regime indicator into one validated, on-demand-refreshable view.

**Architecture:** A Python pipeline (`pipeline/`) runs on a GitHub Actions cron (3×/day, matching TechScreener's existing schedule) and on manual `workflow_dispatch`. Each run fetches swing + insider + market data, validates freshness/completeness, writes one JSON document to a private JSONBin, and sends a Telegram ping (link only, no data) if there's something new. A single-file PWA (`index.html`) on GitHub Pages reads that JSONBin document and renders one sortable table; a Refresh button triggers `workflow_dispatch` via the GitHub API and polls for completion.

**Tech Stack:** Python 3.12 (requests, beautifulsoup4, yfinance, pytz), pytest, vanilla HTML/CSS/JS (no framework, no build step — matches TechScreener/GainerAgent convention), GitHub Actions, GitHub Pages, JSONBin.io v3, Telegram Bot API.

**Reference spec:** `docs/superpowers/specs/2026-07-24-signal-hub-design.md`

---

## Implementation Notes (decisions made while planning)

These resolve the "Offene Punkte" left open in the design spec, plus two deliberate deviations — read before starting:

1. **Freshness threshold:** `MAX_DATA_AGE_DAYS = 4` (not 24h). The scan uses daily EOD bars; a 24h threshold would falsely mark Monday-morning data as stale after a normal weekend. 4 days covers weekends plus a single holiday.
2. **Cron times:** reuse TechScreener's existing schedule (14:00, 17:30, 20:45 UTC = 10:00, 13:30, 16:45 ET, Mo–Fr) — it's already tuned to market hours, no reason to diverge.
3. **No JS/Python parity tests.** The design spec mentions reusing TechScreener's parity mechanism, but that mechanism exists because TechScreener has *two independent implementations* of the same indicators (browser JS + Python bot) that can drift apart. `signal-hub` has only the Python implementation — the dashboard merely displays the finished JSON, it never recomputes indicators. A parity test would have nothing to compare against. Instead, Task 3 and Task 4 use the same deterministic fixtures TechScreener's parity suite uses (copied verbatim) as regression tests, which achieves the actual goal (catch accidental logic drift when the code is touched later) without a nonsensical cross-language comparison.
4. **Secrets are never hardcoded into `index.html`.** The design spec says "Read-Key im Frontend eingebettet." Read literally, that means baking a real key into public GitHub Pages source — which is permanently visible in git history even after rotation. Instead, Task 14 implements the exact pattern TechScreener's own CloudSync already uses successfully: a ⚙ Settings modal where the JSONBin key, Bin ID, and GitHub PAT are entered once and stored in the browser's `localStorage`, never committed to source. Same "no login, private data" outcome, without committing secrets to a public repo.
5. **GitHub PAT scope:** the Personal Access Token used to trigger `workflow_dispatch` from the browser must be a **fine-grained PAT scoped to this one repo only, with "Actions: Read and write" as the only permission** (no code/contents access). Documented in Task 17's README with a rotation reminder. This is called out explicitly because a broadly-scoped token pasted into a browser field is a real risk if the device is compromised — minimal scope caps the blast radius to "someone can trigger scan runs," not "someone can read/write repo code."

---

## Task 1: Repo Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `pipeline/__init__.py`
- Create: `tests/__init__.py`
- Create: `README.md`

- [ ] **Step 1: Create the directory structure and base files**

```bash
mkdir -p pipeline tests .github/workflows
```

`requirements.txt`:
```
requests>=2.31.0
beautifulsoup4>=4.12.0
yfinance>=0.2.40
pytz>=2024.1
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
venv/
.pytest_cache/
```

`pipeline/__init__.py`: empty file.

`tests/__init__.py`: empty file.

`README.md`:
```markdown
# Signal Hub

Konsolidierter Swing-Trading-Signal-Hub: Minervini Trend Template + EMA21 Pullback
(portiert aus TechScreener) + Insider-Trading-Aktivitaet (openinsider.com) + Markt-Ampel,
in einem Dashboard.

Setup-Anleitung folgt in README.md (Task 17 dieses Plans).
```

- [ ] **Step 2: Verify the structure**

Run: `ls pipeline tests .github/workflows`
Expected: `pipeline/__init__.py`, `tests/__init__.py` exist; `.github/workflows` is empty but present.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt requirements-dev.txt .gitignore pipeline/__init__.py tests/__init__.py README.md
git commit -m "chore: scaffold signal-hub repo structure"
```

---

## Task 2: Indicators Module

Ports the three indicator functions actually used downstream (`calc_ema`, `calc_sma`, `calc_atr`, `calc_rs`) from `TechScreener/github-alerts/screener.py`, unchanged. `calc_rsi` is intentionally **not** ported — it exists in the TechScreener bot but is unused there too (YAGNI).

**Files:**
- Create: `pipeline/indicators.py`
- Create: `tests/fixtures.py`
- Test: `tests/test_indicators.py`

- [ ] **Step 1: Write `tests/fixtures.py`** (shared deterministic fixtures, copied from TechScreener's `tests/parity_check.py` fixture generators so later regression tests use identical data)

```python
"""Deterministic fixtures shared across pipeline tests.
The generator functions are copied verbatim from
TechScreener/tests/parity_check.py to keep the swing-logic regression
tests aligned with the source the logic was ported from.
"""


def make_uptrend(n=260, start=50.0, daily_drift=0.002):
    """Generate a deterministic uptrend series."""
    closes = []
    price = start
    for i in range(n):
        noise = ((i * 7 + 3) % 11 - 5) * 0.001
        price = price * (1 + daily_drift + noise)
        closes.append(round(price, 2))
    return closes


def make_downtrend(n=260, start=100.0, daily_drift=-0.001):
    """Generate a deterministic downtrend/sideways series."""
    closes = []
    price = start
    for i in range(n):
        noise = ((i * 7 + 3) % 11 - 5) * 0.001
        price = price * (1 + daily_drift + noise)
        closes.append(round(price, 2))
    return closes


def make_pullback_ohlcv(n=260):
    """Generate OHLCV where the last 3 bars pull back to EMA21, then bounce."""
    closes, opens, highs, lows, volumes = [], [], [], [], []
    price = 50.0
    for i in range(n):
        noise = ((i * 7 + 3) % 11 - 5) * 0.001
        if n - 5 <= i < n - 1:
            drift, vol = -0.005, 800_000
        elif i == n - 1:
            drift, vol = 0.012, 1_200_000
        else:
            drift, vol = 0.002, 1_500_000
        o = price
        c = price * (1 + drift + noise)
        h = max(o, c) * 1.005
        l = min(o, c) * 0.995
        opens.append(round(o, 2))
        closes.append(round(c, 2))
        highs.append(round(h, 2))
        lows.append(round(l, 2))
        volumes.append(vol)
        price = c
    return {'opens': opens, 'closes': closes, 'highs': highs, 'lows': lows, 'volumes': volumes}
```

- [ ] **Step 2: Write the failing test** `tests/test_indicators.py`

```python
from pipeline.indicators import calc_ema, calc_sma, calc_atr, calc_rs


def test_calc_sma_known_values():
    closes = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = calc_sma(closes, 3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == 20.0
    assert result[3] == 30.0
    assert result[4] == 40.0


def test_calc_ema_seeds_with_sma_of_first_period():
    closes = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = calc_ema(closes, 3)
    assert result[2] == 20.0
    assert result[3] is not None
    assert result[4] is not None


def test_calc_rs_positive_when_symbol_outperforms_spy():
    sym = [100.0, 110.0]
    spy = [100.0, 102.0]
    assert calc_rs(sym, spy) == 8.0


def test_calc_rs_none_on_empty_input():
    assert calc_rs([], [100.0, 101.0]) is None
    assert calc_rs([100.0, 101.0], []) is None


def test_calc_atr_positive_for_volatile_series():
    highs = [10, 11, 12, 11, 13]
    lows = [9, 9.5, 10, 9.8, 11]
    closes = [9.5, 10.5, 11.5, 10.2, 12.5]
    atr = calc_atr(highs, lows, closes, period=3)
    assert atr is not None
    assert atr > 0


def test_calc_atr_none_with_insufficient_bars():
    assert calc_atr([10], [9], [9.5], period=14) is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_indicators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.indicators'`

- [ ] **Step 4: Write `pipeline/indicators.py`** (ported unchanged from `TechScreener/github-alerts/screener.py`)

```python
"""Indicator functions ported from TechScreener v23
(github-alerts/screener.py) — kept byte-identical to the source of truth.
Only the functions actually used by signal-hub's swing scan are ported.
"""


def calc_ema(arr, period):
    k = 2 / (period + 1)
    result = [None] * len(arr)
    if len(arr) < period:
        return result
    sma = sum(v for v in arr[:period] if v is not None) / period
    result[period - 1] = sma
    for i in range(period, len(arr)):
        v = arr[i] if arr[i] is not None else 0
        result[i] = v * k + result[i - 1] * (1 - k)
    return result


def calc_sma(arr, period):
    result = [None] * len(arr)
    if len(arr) < period:
        return result
    s = sum(arr[:period])
    result[period - 1] = s / period
    for i in range(period, len(arr)):
        s += (arr[i] or 0) - (arr[i - period] or 0)
        result[i] = s / period
    return result


def calc_atr(highs, lows, closes, period=14):
    n = len(closes)
    if n < 2:
        return None
    trs = []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    atr_arr = calc_ema(trs, period)
    return atr_arr[-1]


def calc_rs(sym_closes, spy_closes):
    if not sym_closes or not spy_closes or len(sym_closes) < 2 or len(spy_closes) < 2:
        return None
    n = min(len(sym_closes), len(spy_closes))
    sym_ret = (sym_closes[-1] - sym_closes[-n]) / sym_closes[-n] * 100
    spy_ret = (spy_closes[-1] - spy_closes[-n]) / spy_closes[-n] * 100
    return round(sym_ret - spy_ret, 1)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_indicators.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add pipeline/indicators.py tests/fixtures.py tests/test_indicators.py
git commit -m "feat: port indicator functions from TechScreener"
```

---

## Task 3: Data Quality Module (`validate.py`)

**Files:**
- Create: `pipeline/validate.py`
- Test: `tests/test_validate.py`

- [ ] **Step 1: Write the failing test** `tests/test_validate.py`

```python
from datetime import date, timedelta
from pipeline.validate import validate_symbol, determine_run_status, MAX_DATA_AGE_DAYS


def test_validate_symbol_fresh_with_recent_full_history():
    closes = [100.0 + i * 0.1 for i in range(260)]
    quality, reason = validate_symbol(date.today(), closes)
    assert quality == 'fresh'
    assert reason is None


def test_validate_symbol_stale_with_insufficient_history():
    closes = [100.0] * 100
    quality, reason = validate_symbol(date.today(), closes)
    assert quality == 'stale'
    assert '100' in reason


def test_validate_symbol_stale_when_data_too_old():
    closes = [100.0 + i * 0.1 for i in range(260)]
    old_date = date.today() - timedelta(days=MAX_DATA_AGE_DAYS + 1)
    quality, reason = validate_symbol(old_date, closes)
    assert quality == 'stale'
    assert reason is not None


def test_validate_symbol_stale_with_no_date():
    closes = [100.0 + i * 0.1 for i in range(260)]
    quality, reason = validate_symbol(None, closes)
    assert quality == 'stale'


def test_validate_symbol_stale_with_gaps_in_recent_data():
    closes = [100.0 + i * 0.1 for i in range(260)]
    closes[-1] = None
    quality, reason = validate_symbol(date.today(), closes)
    assert quality == 'stale'


def test_determine_run_status_ok_when_all_sources_succeed():
    assert determine_run_status({'swing_scan': 'ok', 'insider_scan': 'ok'}) == 'ok'


def test_determine_run_status_partial_when_some_fail():
    assert determine_run_status({'swing_scan': 'ok', 'insider_scan': 'failed'}) == 'partial'


def test_determine_run_status_failed_when_all_fail():
    assert determine_run_status({'swing_scan': 'failed', 'insider_scan': 'failed'}) == 'failed'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.validate'`

- [ ] **Step 3: Write `pipeline/validate.py`**

```python
"""Data quality gate for the swing scan. Runs per-symbol before a result
is written into the JSONBin document, and aggregates per-source run
status into an overall run_status for meta.run_status.
"""
from datetime import date, datetime, timezone

MAX_DATA_AGE_DAYS = 4  # covers a normal weekend + one holiday; daily EOD bars only
MIN_TREND_TEMPLATE_BARS = 252


def validate_symbol(last_close_date, closes):
    """Validate a symbol's daily close history before it's used for the swing scan.

    Args:
        last_close_date: date of the most recent bar, or None if unknown.
        closes: list of daily close prices (most recent last).

    Returns:
        (quality, reason) where quality is 'fresh' or 'stale', and reason is
        a human-readable string when quality == 'stale', else None.
    """
    if not closes or len(closes) < MIN_TREND_TEMPLATE_BARS:
        n = len(closes) if closes else 0
        return 'stale', f'Nur {n} Handelstage verfuegbar (<{MIN_TREND_TEMPLATE_BARS})'

    if any(c is None for c in closes[-MIN_TREND_TEMPLATE_BARS:]):
        return 'stale', 'Luecken in den letzten 252 Kursdaten'

    if last_close_date is None:
        return 'stale', 'Kein Datum fuer den letzten Kurs bekannt'

    age_days = (datetime.now(timezone.utc).date() - last_close_date).days
    if age_days > MAX_DATA_AGE_DAYS:
        return 'stale', f'Kursdaten {age_days} Tage alt (Schwellwert {MAX_DATA_AGE_DAYS})'

    return 'fresh', None


def determine_run_status(source_statuses):
    """Aggregate per-source 'ok'/'failed' statuses into an overall run status.

    Args:
        source_statuses: dict of {source_name: 'ok' | 'failed'}.

    Returns:
        'ok' if every source succeeded, 'failed' if every source failed,
        else 'partial'.
    """
    values = list(source_statuses.values())
    if values and all(v == 'ok' for v in values):
        return 'ok'
    if values and all(v == 'failed' for v in values):
        return 'failed'
    return 'partial'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validate.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/validate.py tests/test_validate.py
git commit -m "feat: add data quality validation module"
```

---

## Task 4: Swing Scan — Trend Template & EMA21 Pullback Logic

Ports `check_trend_template` and `detect_ema21_pullback` from `TechScreener/github-alerts/screener.py`, unchanged. These are pure functions (no I/O), tested with the fixtures from Task 2.

**Files:**
- Create: `pipeline/swing_scan.py`
- Test: `tests/test_swing_scan.py`

- [ ] **Step 1: Write the failing test** `tests/test_swing_scan.py`

```python
from pipeline.swing_scan import check_trend_template, detect_ema21_pullback
from tests.fixtures import make_uptrend, make_downtrend, make_pullback_ohlcv


def test_trend_template_passes_on_clear_uptrend():
    closes = make_uptrend(260, 50.0, 0.002)
    passed, criteria = check_trend_template(closes)
    assert passed is True
    assert all(criteria)
    assert len(criteria) == 6


def test_trend_template_fails_on_downtrend():
    closes = make_downtrend(260, 100.0, -0.001)
    passed, criteria = check_trend_template(closes)
    assert passed is False


def test_trend_template_fails_with_insufficient_history():
    closes = make_uptrend(200, 50.0, 0.003)
    passed, criteria = check_trend_template(closes)
    assert passed is False
    assert criteria == [False] * 6


def test_ema21_pullback_detects_signal_on_pullback_and_bounce():
    ohlcv = make_pullback_ohlcv(260)
    signal = detect_ema21_pullback(
        ohlcv['closes'], ohlcv['opens'], ohlcv['highs'], ohlcv['lows'], ohlcv['volumes'],
        spy_sma50_ok=True,
    )
    assert signal is not None
    assert signal['entry'] > signal['stop']
    assert 0 < signal['stop_dist'] <= 8


def test_ema21_pullback_returns_none_when_spy_bearish():
    ohlcv = make_pullback_ohlcv(260)
    signal = detect_ema21_pullback(
        ohlcv['closes'], ohlcv['opens'], ohlcv['highs'], ohlcv['lows'], ohlcv['volumes'],
        spy_sma50_ok=False,
    )
    assert signal is None


def test_ema21_pullback_returns_none_on_downtrend():
    closes = make_downtrend(260, 100.0, -0.001)
    n = len(closes)
    opens = closes[:]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]
    volumes = [1_000_000] * n
    signal = detect_ema21_pullback(closes, opens, highs, lows, volumes, spy_sma50_ok=True)
    assert signal is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_swing_scan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.swing_scan'`

- [ ] **Step 3: Write `pipeline/swing_scan.py`** (part 1 — pure logic; I/O functions added in Task 5)

```python
"""Swing scan: Minervini Trend Template + EMA21 Pullback.
check_trend_template and detect_ema21_pullback are ported unchanged from
TechScreener v23 (github-alerts/screener.py) — do not alter the logic here
without also updating the source and re-running tests/test_swing_scan.py.
"""
from pipeline.indicators import calc_ema, calc_sma, calc_atr


def check_trend_template(closes):
    n = len(closes)
    if n < 252:
        return False, [False] * 6

    sma150 = calc_sma(closes, 150)
    sma200 = calc_sma(closes, 200)
    cur = closes[-1]
    s150 = sma150[-1]
    s200 = sma200[-1]

    if s150 is None or s200 is None:
        return False, [False] * 6

    c1 = cur > s150
    c2 = cur > s200
    c3 = s150 > s200
    s200_ago = sma200[-22] if len(sma200) >= 22 else None
    c4 = s200_ago is not None and s200 > s200_ago
    low52w = min(closes[-252:])
    c5 = cur >= low52w * 1.25
    high52w = max(closes[-252:])
    c6 = cur >= high52w * 0.75

    criteria = [c1, c2, c3, c4, c5, c6]
    return all(criteria), criteria


def detect_ema21_pullback(closes, opens, highs, lows, volumes, spy_sma50_ok):
    n = len(closes)
    if n < 50:
        return None

    if not spy_sma50_ok:
        return None

    tt_pass, tt_criteria = check_trend_template(closes)
    if not tt_pass:
        return None

    ema21 = calc_ema(closes, 21)
    if ema21[-1] is None:
        return None

    cur = closes[-1]

    touched = False
    for i in range(max(0, n - 3), n):
        if ema21[i] is not None and (lows[i] <= ema21[i] or closes[i] <= ema21[i]):
            touched = True
            break
    if not touched:
        return None

    if cur <= ema21[-1]:
        return None

    avg_vol20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 0
    pb_vol = sum(volumes[-3:]) / 3
    if avg_vol20 > 0 and pb_vol >= avg_vol20:
        return None

    if cur <= opens[-1]:
        return None

    entry = cur
    pb_low = min(lows[-5:])
    atr = calc_atr(highs, lows, closes, 14)
    buffer = atr if atr else entry * 0.005
    stop = round(pb_low - buffer * 0.5, 2)
    stop_dist = (entry - stop) / entry * 100

    if stop_dist > 8 or stop_dist <= 0:
        return None

    vol_drop = round((1 - pb_vol / avg_vol20) * 100) if avg_vol20 > 0 else 0

    pb_days = 0
    for i in range(n - 1, max(0, n - 10), -1):
        if ema21[i] is not None and (lows[i] <= ema21[i] or closes[i] <= ema21[i]):
            pb_days += 1
        elif pb_days > 0:
            break

    ema10 = calc_ema(closes, 10)
    trail = round(ema10[-1], 2) if ema10[-1] is not None else None

    return {
        'entry': round(entry, 2),
        'stop': stop,
        'stop_dist': round(stop_dist, 1),
        'trail_ema10': trail,
        'vol_drop': vol_drop,
        'pb_days': max(pb_days, 1),
        'criteria': tt_criteria,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_swing_scan.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/swing_scan.py tests/test_swing_scan.py
git commit -m "feat: port trend template and EMA21 pullback logic"
```

---

## Task 5: Swing Scan — Universe & Per-Symbol Fetch

Adds the universe constant (byte-identical to TechScreener's `CORE_UNIVERSE`/`UNIVERSE`) and the I/O layer that fetches OHLCV via yfinance, runs it through `validate.validate_symbol`, and builds the per-symbol result dict for the JSONBin document.

**Files:**
- Modify: `pipeline/swing_scan.py`
- Test: `tests/test_swing_scan.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_swing_scan.py`

```python
from unittest.mock import patch, MagicMock
import pandas as pd
from pipeline.swing_scan import scan_symbol, UNIVERSE
from tests.fixtures import make_uptrend


def _make_history_df(closes):
    n = len(closes)
    dates = pd.date_range(end=pd.Timestamp.utcnow().normalize(), periods=n, freq='D')
    return pd.DataFrame({
        'Open': closes,
        'High': [c * 1.01 for c in closes],
        'Low': [c * 0.99 for c in closes],
        'Close': closes,
        'Volume': [1_000_000] * n,
    }, index=dates)


def test_universe_is_nonempty_and_uppercase():
    assert len(UNIVERSE) > 0
    assert all(sym == sym.upper() for sym in UNIVERSE)


def test_scan_symbol_marks_stale_on_empty_history():
    with patch('pipeline.swing_scan.yf.Ticker') as mock_ticker:
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        result = scan_symbol('XYZ', spy_sma50_ok=True, spy_closes=None)
    assert result['data_quality'] == 'stale'
    assert result['swing'] is None
    assert 'data_quality_reason' in result


def test_scan_symbol_returns_swing_result_on_sufficient_history():
    closes = make_uptrend(260, 50.0, 0.002)
    df = _make_history_df(closes)
    with patch('pipeline.swing_scan.yf.Ticker') as mock_ticker:
        mock_ticker.return_value.history.return_value = df
        result = scan_symbol('CAVA', spy_sma50_ok=True, spy_closes=closes)
    assert result['data_quality'] == 'fresh'
    assert result['swing']['template_pass'] is True
    assert result['price'] == round(closes[-1], 2)


def test_scan_symbol_handles_fetch_exception():
    with patch('pipeline.swing_scan.yf.Ticker') as mock_ticker:
        mock_ticker.return_value.history.side_effect = RuntimeError('network error')
        result = scan_symbol('CAVA', spy_sma50_ok=True, spy_closes=None)
    assert result['data_quality'] == 'stale'
    assert 'network error' in result['data_quality_reason']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_swing_scan.py -v`
Expected: FAIL with `ImportError: cannot import name 'scan_symbol'`

(Note: this step requires `pandas` for the test's DataFrame fixture, which `yfinance` already depends on transitively — no new dependency needed.)

- [ ] **Step 3: Append to `pipeline/swing_scan.py`**

```python
import yfinance as yf

from pipeline import validate

UNIVERSE = [
    # KERN: US Mid-Cap Growth
    'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST', 'RBLX', 'ZETA', 'SMCI',
    'CAVA', 'DUOL', 'CELH', 'HIMS', 'GTLB', 'PATH',
    # VOLATILE LARGE-CAPS
    'TSLA', 'AMD', 'PLTR', 'CRWD', 'NET', 'DDOG', 'SNOW', 'AXON', 'PANW', 'CRM', 'ADBE',
    # BRANCHEN-DIVERSIFIKATION
    'ENPH', 'DKNG', 'ABNB', 'MELI', 'NU', 'SHOP', 'ROKU', 'DASH',
    # Mid-Cap Growth Erweiterung
    'ONON', 'BILL', 'MNDY', 'CFLT', 'GRAB', 'TOST', 'ARM', 'BIRK',
    'CART', 'IOT', 'DOCS', 'PCOR', 'GLBE', 'RELY', 'TMDX', 'KVYO', 'CWAN', 'ASAN', 'BRZE',
    # Volatile Large-Caps
    'NVDA', 'META', 'GOOGL', 'AMZN', 'NFLX', 'UBER', 'SQ', 'SPOT',
    'PINS', 'SNAP', 'ZS', 'FTNT', 'WDAY', 'NOW', 'INTU',
    # Sektor-Diversifikation
    'LLY', 'VST', 'CEG', 'FSLR', 'GEV', 'TRGP', 'EME', 'PWR',
    'DECK', 'WING', 'ELF', 'LULU', 'PSTG', 'ANET', 'MSTR',
]


def scan_symbol(sym, spy_sma50_ok, spy_closes):
    """Fetch + evaluate a single symbol's swing setup.

    Returns a dict with keys 'price', 'swing', 'data_quality',
    and optionally 'data_quality_reason'. Never raises — fetch/parse
    errors are captured and surfaced as a 'stale' result instead.
    """
    try:
        hist = yf.Ticker(sym).history(period='1y', interval='1d', auto_adjust=True)
    except Exception as e:
        return {
            'price': None,
            'swing': None,
            'data_quality': 'stale',
            'data_quality_reason': f'Fehler beim Laden: {e}',
        }

    if hist.empty:
        return {
            'price': None,
            'swing': None,
            'data_quality': 'stale',
            'data_quality_reason': 'Keine Kursdaten von Yahoo Finance',
        }

    closes = hist['Close'].tolist()
    opens = hist['Open'].tolist()
    highs = hist['High'].tolist()
    lows = hist['Low'].tolist()
    volumes = hist['Volume'].tolist()
    last_date = hist.index[-1].date()

    quality, reason = validate.validate_symbol(last_date, closes)

    result = {'price': round(closes[-1], 2), 'data_quality': quality}
    if reason:
        result['data_quality_reason'] = reason

    if quality == 'stale':
        result['swing'] = None
        return result

    tt_pass, tt_criteria = check_trend_template(closes)
    rs = None
    if spy_closes:
        from pipeline.indicators import calc_rs
        rs = calc_rs(closes[-126:], spy_closes[-126:])
    signal = detect_ema21_pullback(closes, opens, highs, lows, volumes, spy_sma50_ok) if tt_pass else None

    result['swing'] = {
        'template_pass': tt_pass,
        'criteria': tt_criteria,
        'rs_spy': rs,
        'signal': 'buy' if signal else '-',
    }
    if signal:
        result['swing']['entry'] = signal['entry']
        result['swing']['stop'] = signal['stop']
        result['swing']['trail'] = signal['trail_ema10']

    return result


def run_swing_scan(spy_sma50_ok, spy_closes):
    """Scan every symbol in UNIVERSE. Returns {sym: scan_symbol_result}."""
    return {sym: scan_symbol(sym, spy_sma50_ok, spy_closes) for sym in UNIVERSE}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_swing_scan.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/swing_scan.py tests/test_swing_scan.py
git commit -m "feat: add swing scan universe and per-symbol fetch"
```

---

## Task 6: Market Ampel Module

**Files:**
- Create: `pipeline/market_ampel.py`
- Test: `tests/test_market_ampel.py`

- [ ] **Step 1: Write the failing test** `tests/test_market_ampel.py`

```python
from unittest.mock import patch
import pandas as pd
from pipeline.market_ampel import run_market_ampel
from tests.fixtures import make_uptrend, make_downtrend


def _make_history_df(closes):
    n = len(closes)
    dates = pd.date_range(end=pd.Timestamp.utcnow().normalize(), periods=n, freq='D')
    return pd.DataFrame({'Close': closes}, index=dates)


def test_market_ampel_bull_when_spy_above_sma50():
    closes = make_uptrend(260, 400.0, 0.002)
    with patch('pipeline.market_ampel.yf.Ticker') as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_history_df(closes)
        result = run_market_ampel()
    assert result['spy_regime'] == 'bull'
    assert result['spy_sma50_ok'] is True


def test_market_ampel_bear_when_spy_below_sma50():
    closes = make_downtrend(260, 500.0, -0.002)
    with patch('pipeline.market_ampel.yf.Ticker') as mock_ticker:
        mock_ticker.return_value.history.return_value = _make_history_df(closes)
        result = run_market_ampel()
    assert result['spy_regime'] == 'bear'
    assert result['spy_sma50_ok'] is False


def test_market_ampel_raises_on_empty_history():
    with patch('pipeline.market_ampel.yf.Ticker') as mock_ticker:
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        try:
            run_market_ampel()
            assert False, 'expected RuntimeError'
        except RuntimeError:
            pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_market_ampel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.market_ampel'`

- [ ] **Step 3: Write `pipeline/market_ampel.py`**

```python
"""Market regime check: is SPY above its 50-day SMA?
Ported from the spy_sma50_ok gate in TechScreener's github-alerts/screener.py.
"""
import yfinance as yf

from pipeline.indicators import calc_sma


def run_market_ampel():
    hist = yf.Ticker('SPY').history(period='1y', interval='1d', auto_adjust=True)
    if hist.empty:
        raise RuntimeError('Keine SPY-Daten von Yahoo Finance')

    closes = hist['Close'].tolist()
    sma50 = calc_sma(closes, 50)
    spy_sma50_ok = sma50[-1] is not None and closes[-1] > sma50[-1]

    return {
        'spy_price': round(closes[-1], 2),
        'spy_sma50': round(sma50[-1], 2) if sma50[-1] is not None else None,
        'spy_regime': 'bull' if spy_sma50_ok else 'bear',
        'spy_sma50_ok': spy_sma50_ok,
        'spy_closes': closes,  # consumed by swing_scan for RS calc; stripped before JSONBin write
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_market_ampel.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/market_ampel.py tests/test_market_ampel.py
git commit -m "feat: add market ampel (SPY regime) module"
```

---

## Task 7: Insider Scan Module

Uses openinsider.com's two bulk list pages instead of per-symbol requests — verified against the live site's actual table structure (17 columns, `table.tinytable` CSS class):

- `latest-insider-purchases-25k` — filtered locally to symbols in `UNIVERSE`.
- `latest-cluster-buys` — filtered locally to symbols **outside** `UNIVERSE` with ≥2 distinct insiders (the "Zusatzliste" from the design spec).

**Files:**
- Create: `pipeline/insider_scan.py`
- Test: `tests/test_insider_scan.py`

- [ ] **Step 1: Write the failing test** `tests/test_insider_scan.py`

```python
from unittest.mock import patch, Mock
from pipeline.insider_scan import (
    parse_value,
    fetch_openinsider_table,
    fetch_universe_purchases,
    fetch_cluster_buys_outside_universe,
    run_insider_scan,
)

PURCHASES_HTML = """
<html><body>
<table class="tinytable">
<tr><th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Company Name</th>
<th>Insider Name</th><th>Title</th><th>Trade Type</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>ΔOwn</th><th>Value</th><th>1d</th><th>1w</th><th>1m</th><th>6m</th></tr>
<tr><td>M</td><td>2026-07-23 21:22:32</td><td>2026-07-21</td><td>CAVA</td>
<td>Cava Group, Inc.</td><td>Jane Doe</td><td>CEO</td><td>P - Purchase</td>
<td>$9.76</td><td>+10,000</td><td>50,000</td><td>+25%</td><td>+$97,600</td>
<td></td><td></td><td></td><td></td></tr>
<tr><td>A</td><td>2026-07-23 20:00:00</td><td>2026-07-20</td><td>CAVA</td>
<td>Cava Group, Inc.</td><td>John Roe</td><td>Dir</td><td>P - Purchase</td>
<td>$9.50</td><td>+500</td><td>10,000</td><td>+5%</td><td>+$4,750</td>
<td></td><td></td><td></td><td></td></tr>
<tr><td></td><td>2026-07-23 19:00:00</td><td>2026-07-20</td><td>XYZ</td>
<td>Some Corp</td><td>John Roe</td><td>Dir</td><td>S - Sale</td>
<td>$5.00</td><td>-1,000</td><td>1,000</td><td>-10%</td><td>-$5,000</td>
<td></td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""

CLUSTER_HTML = """
<html><body>
<table class="tinytable">
<tr><th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Company Name</th>
<th>Industry</th><th>Ins</th><th>Trade Type</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>ΔOwn</th><th>Value</th><th>1d</th><th>1w</th><th>1m</th><th>6m</th></tr>
<tr><td>M</td><td>2026-07-23 18:47:22</td><td>2026-07-22</td><td>BYRN</td>
<td>Byrna Technologies Inc.</td><td>Misc. Electrical</td><td>3</td><td>P - Purchase</td>
<td>$3.48</td><td>+72,789</td><td>377,652</td><td>+24%</td><td>+$253,222</td>
<td></td><td></td><td></td><td></td></tr>
<tr><td>D</td><td>2026-07-23 16:24:22</td><td>2026-07-22</td><td>ONE</td>
<td>Solo Insider Corp</td><td>Banks</td><td>1</td><td>P - Purchase</td>
<td>$11.95</td><td>+5,000</td><td>10,000</td><td>+75%</td><td>+$59,750</td>
<td></td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""


def _mock_get(html):
    resp = Mock(status_code=200, text=html)
    resp.raise_for_status = Mock()
    return resp


def test_parse_value_handles_currency_formatting():
    assert parse_value('+$2,583,314') == 2583314.0
    assert parse_value('-$1,380,764') == -1380764.0
    assert parse_value('') is None
    assert parse_value(None) is None


def test_fetch_openinsider_table_parses_rows_into_dicts():
    with patch('pipeline.insider_scan.requests.get', return_value=_mock_get(PURCHASES_HTML)):
        rows = fetch_openinsider_table('http://openinsider.com/latest-insider-purchases-25k')
    assert len(rows) == 3
    assert rows[0]['Ticker'] == 'CAVA'
    assert rows[0]['Trade Type'] == 'P - Purchase'


def test_fetch_universe_purchases_filters_universe_type_and_min_value():
    with patch('pipeline.insider_scan.requests.get', return_value=_mock_get(PURCHASES_HTML)):
        trades = fetch_universe_purchases(['CAVA', 'TSLA'])
    # XYZ excluded (not in universe), sale rows excluded even if they were in universe
    assert {t['sym'] for t in trades} == {'CAVA'}
    assert len(trades) == 2
    assert all(t['value'] > 0 for t in trades)


def test_fetch_cluster_buys_outside_universe_requires_min_insiders():
    with patch('pipeline.insider_scan.requests.get', return_value=_mock_get(CLUSTER_HTML)):
        clusters = fetch_cluster_buys_outside_universe(['CAVA'], min_insiders=2)
    syms = {c['sym'] for c in clusters}
    assert 'BYRN' in syms   # 3 insiders, passes
    assert 'ONE' not in syms  # only 1 insider, filtered out


def test_run_insider_scan_merges_universe_and_cluster_results():
    def side_effect(url, headers=None, timeout=None):
        if 'cluster' in url:
            return _mock_get(CLUSTER_HTML)
        return _mock_get(PURCHASES_HTML)

    with patch('pipeline.insider_scan.requests.get', side_effect=side_effect):
        result = run_insider_scan(['CAVA'])

    assert 'CAVA' in result
    assert result['CAVA']['cluster_buy'] is True  # 2 distinct insiders in PURCHASES_HTML
    assert 'BYRN' in result
    assert result['BYRN']['cluster_buy'] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_insider_scan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.insider_scan'`

- [ ] **Step 3: Write `pipeline/insider_scan.py`**

```python
"""Insider trading scan via openinsider.com's bulk list pages.
Verified table structure (2026-07-24, table.tinytable class, 17 columns):
Filing Date, Trade Date, Ticker, Company Name, [Insider Name|Industry],
[Title|Ins], Trade Type, Price, Qty, Owned, DeltaOwn, Value, 1d, 1w, 1m, 6m.
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (SignalHub Bot)'}
PURCHASES_URL = 'http://openinsider.com/latest-insider-purchases-25k'
CLUSTER_BUYS_URL = 'http://openinsider.com/latest-cluster-buys'
MIN_TRADE_VALUE = 50_000


def parse_value(text):
    """Parse a Value cell like '+$2,583,314' into a float, or None if unparseable."""
    if not text:
        return None
    cleaned = text.replace('$', '').replace(',', '').replace('+', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_openinsider_table(url):
    """Fetch an openinsider.com list page and return rows as header-keyed dicts."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table', class_='tinytable')
    if table is None:
        return []
    rows = table.find_all('tr')
    if not rows:
        return []
    headers = [th.text.strip() for th in rows[0].find_all('th')]
    result = []
    for row in rows[1:]:
        cells = row.find_all('td')
        if len(cells) != len(headers):
            continue
        values = [c.text.strip() for c in cells]
        result.append(dict(zip(headers, values)))
    return result


def fetch_universe_purchases(universe):
    """Latest insider purchases filtered to symbols in `universe`, purchases only.

    No MIN_TRADE_VALUE filter here: this is the curated ~80-symbol watchlist,
    where any insider purchase is worth surfacing. The value filter only
    applies to fetch_cluster_buys_outside_universe, which scans the broad,
    noisy market-wide feed and needs it to cut noise.
    """
    universe_set = {s.upper() for s in universe}
    trades = []
    for row in fetch_openinsider_table(PURCHASES_URL):
        ticker = row.get('Ticker', '').upper()
        if ticker not in universe_set:
            continue
        if not row.get('Trade Type', '').startswith('P'):
            continue
        value = parse_value(row.get('Value', ''))
        if value is None:
            continue
        trades.append({
            'sym': ticker,
            'insider': row.get('Insider Name', ''),
            'role': row.get('Title', ''),
            'value': abs(value),
            'transacted': row.get('Trade Date', ''),
            'filed': row.get('Filing Date', ''),
        })
    return trades


def fetch_cluster_buys_outside_universe(universe, min_insiders=2):
    """Latest cluster buys for symbols NOT in `universe`, requiring at least
    `min_insiders` distinct buyers and MIN_TRADE_VALUE per trade."""
    universe_set = {s.upper() for s in universe}
    grouped = {}
    for row in fetch_openinsider_table(CLUSTER_BUYS_URL):
        ticker = row.get('Ticker', '').upper()
        if ticker in universe_set:
            continue
        try:
            ins_count = int(row.get('Ins', '0') or '0')
        except ValueError:
            ins_count = 0
        if ins_count < min_insiders:
            continue
        value = parse_value(row.get('Value', ''))
        if value is None or abs(value) < MIN_TRADE_VALUE:
            continue
        entry = grouped.setdefault(ticker, {'sym': ticker, 'insider_count': ins_count, 'trades': []})
        entry['trades'].append({
            'value': abs(value),
            'transacted': row.get('Trade Date', ''),
            'filed': row.get('Filing Date', ''),
        })
    return list(grouped.values())


def _group_universe_trades(trades):
    grouped = {}
    for t in trades:
        sym = t['sym']
        entry = grouped.setdefault(sym, {'trades': []})
        entry['trades'].append({k: v for k, v in t.items() if k != 'sym'})
    for sym, data in grouped.items():
        distinct_insiders = {tr['insider'] for tr in data['trades'] if tr.get('insider')}
        data['cluster_buy'] = len(distinct_insiders) >= 2
        data['insider_count'] = len(distinct_insiders)
    return grouped


def run_insider_scan(universe):
    """Full insider scan: universe purchases + cluster buys outside universe.
    Returns {sym: {cluster_buy: bool, trades: [...], insider_count: int}}
    ready for the symbols section of the JSONBin document.

    The two source pages are fetched independently: a failure on one
    (network error, site layout change, rate limit) does not discard
    results already fetched from the other — it's logged and treated as
    an empty result for that source instead.
    """
    try:
        universe_trades = fetch_universe_purchases(universe)
    except Exception as e:
        print(f'insider_scan: fetch_universe_purchases failed: {e}')
        universe_trades = []
    result = _group_universe_trades(universe_trades)

    try:
        cluster_entries = fetch_cluster_buys_outside_universe(universe)
    except Exception as e:
        print(f'insider_scan: fetch_cluster_buys_outside_universe failed: {e}')
        cluster_entries = []

    for entry in cluster_entries:
        result[entry['sym']] = {
            'cluster_buy': True,
            'insider_count': entry['insider_count'],
            'trades': entry['trades'],
        }

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_insider_scan.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/insider_scan.py tests/test_insider_scan.py
git commit -m "feat: add openinsider.com insider trading scan"
```

---

## Task 8: JSONBin Client

**Files:**
- Create: `pipeline/jsonbin_client.py`
- Test: `tests/test_jsonbin_client.py`

- [ ] **Step 1: Write the failing test** `tests/test_jsonbin_client.py`

```python
from unittest.mock import patch, Mock
import pytest
from pipeline import jsonbin_client


def test_read_bin_returns_record(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', 'testkey')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', 'testbin')
    resp = Mock(status_code=200)
    resp.json.return_value = {'record': {'foo': 'bar'}}
    resp.raise_for_status = Mock()
    with patch('pipeline.jsonbin_client.requests.get', return_value=resp):
        result = jsonbin_client.read_bin()
    assert result == {'foo': 'bar'}


def test_read_bin_raises_without_credentials(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', '')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', '')
    with pytest.raises(RuntimeError):
        jsonbin_client.read_bin()


def test_write_bin_sends_put_with_document(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', 'testkey')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', 'testbin')
    resp = Mock(status_code=200)
    resp.raise_for_status = Mock()
    with patch('pipeline.jsonbin_client.requests.put', return_value=resp) as mock_put:
        result = jsonbin_client.write_bin({'foo': 'bar'})
    assert result is True
    mock_put.assert_called_once()
    assert mock_put.call_args.kwargs['json'] == {'foo': 'bar'}


def test_write_bin_raises_without_credentials(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', '')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', '')
    with pytest.raises(RuntimeError):
        jsonbin_client.write_bin({'foo': 'bar'})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jsonbin_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.jsonbin_client'`

- [ ] **Step 3: Write `pipeline/jsonbin_client.py`**

```python
"""JSONBin.io v3 client. Same read/write pattern as
TechScreener/github-alerts/screener.py's read_positions_from_jsonbin /
write_candidates_to_jsonbin, generalized to a whole-document read/write.
"""
import os

import requests

JSONBIN_KEY = os.environ.get('JSONBIN_MASTER_KEY', '')
JSONBIN_BIN = os.environ.get('JSONBIN_BIN_ID', '')
BASE_URL = 'https://api.jsonbin.io/v3/b'


def read_bin():
    """Read the current JSONBin document. Raises RuntimeError if credentials
    are missing, or requests.HTTPError on a non-2xx response."""
    if not JSONBIN_KEY or not JSONBIN_BIN:
        raise RuntimeError('JSONBIN_MASTER_KEY oder JSONBIN_BIN_ID nicht gesetzt')
    resp = requests.get(
        f'{BASE_URL}/{JSONBIN_BIN}/latest',
        headers={'X-Master-Key': JSONBIN_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get('record', {})


def write_bin(document):
    """Overwrite the JSONBin document. Raises RuntimeError if credentials
    are missing, or requests.HTTPError on a non-2xx response."""
    if not JSONBIN_KEY or not JSONBIN_BIN:
        raise RuntimeError('JSONBIN_MASTER_KEY oder JSONBIN_BIN_ID nicht gesetzt')
    resp = requests.put(
        f'{BASE_URL}/{JSONBIN_BIN}',
        json=document,
        headers={'X-Master-Key': JSONBIN_KEY, 'Content-Type': 'application/json'},
        timeout=15,
    )
    resp.raise_for_status()
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jsonbin_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/jsonbin_client.py tests/test_jsonbin_client.py
git commit -m "feat: add JSONBin read/write client"
```

---

## Task 9: Telegram Notification Module

Only a "klingel" — link, no data — per the design's consolidation goal.

**Files:**
- Create: `pipeline/telegram_notify.py`
- Test: `tests/test_telegram_notify.py`

- [ ] **Step 1: Write the failing test** `tests/test_telegram_notify.py`

```python
from pipeline.telegram_notify import build_notification


def test_build_notification_none_when_nothing_new():
    assert build_notification(0, 0, 'https://example.com') is None


def test_build_notification_singular_signal_wording():
    msg = build_notification(1, 0, 'https://example.com')
    assert '1 neues Swing-Signal' in msg
    assert 'Signale' not in msg


def test_build_notification_plural_signal_wording():
    msg = build_notification(3, 0, 'https://example.com')
    assert '3 neue Swing-Signale' in msg


def test_build_notification_includes_insider_count_and_link():
    msg = build_notification(0, 1, 'https://example.com')
    assert '1 neuer Insider-Cluster-Buy' in msg
    assert 'https://example.com' in msg


def test_build_notification_plural_insider_wording():
    msg = build_notification(0, 2, 'https://example.com')
    assert '2 neue Insider-Cluster-Buys' in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram_notify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.telegram_notify'`

- [ ] **Step 3: Write `pipeline/telegram_notify.py`**

```python
"""Telegram notification: a link, not a report. The actual data lives in the
dashboard — Telegram's only job is to say "something changed, go look"."""
import os

import requests

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')


def build_notification(new_signals_count, new_insider_count, dashboard_url):
    """Build the notification text, or return None if there's nothing new
    to report (caller should skip sending in that case)."""
    if new_signals_count == 0 and new_insider_count == 0:
        return None

    parts = ['\U0001f514 <b>Signal Hub Update</b>']

    if new_signals_count == 1:
        parts.append('1 neues Swing-Signal')
    elif new_signals_count > 1:
        parts.append(f'{new_signals_count} neue Swing-Signale')

    if new_insider_count == 1:
        parts.append('1 neuer Insider-Cluster-Buy')
    elif new_insider_count > 1:
        parts.append(f'{new_insider_count} neue Insider-Cluster-Buys')

    parts.append(f'→ {dashboard_url}')
    return '\n'.join(parts)


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print('TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt')
        return False
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    resp = requests.post(url, json=payload, timeout=10)
    return resp.status_code == 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram_notify.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/telegram_notify.py tests/test_telegram_notify.py
git commit -m "feat: add telegram link-only notification module"
```

---

## Task 10: Build Orchestrator

Wires every module together: fetch market ampel → swing scan → insider scan, validate, diff against the previous JSONBin document to detect what's new, write the new document, notify if something changed.

**Files:**
- Create: `pipeline/build.py`
- Test: `tests/test_build.py`

- [ ] **Step 1: Write the failing test** `tests/test_build.py`

```python
from unittest.mock import patch
from pipeline.build import run, DASHBOARD_URL


def _patch_all(market_ok=True, swing_ok=True, insider_ok=True, prev_symbols=None):
    if prev_symbols is None:
        prev_symbols = {}
    patches = []
    if market_ok:
        patches.append(patch('pipeline.build.market_ampel.run_market_ampel', return_value={
            'spy_price': 500.0, 'spy_sma50': 490.0, 'spy_regime': 'bull',
            'spy_sma50_ok': True, 'spy_closes': [490.0, 495.0, 500.0],
        }))
    else:
        patches.append(patch('pipeline.build.market_ampel.run_market_ampel', side_effect=RuntimeError('spy down')))

    if swing_ok:
        patches.append(patch('pipeline.build.swing_scan.run_swing_scan', return_value={
            'CAVA': {'price': 100.0, 'data_quality': 'fresh',
                     'swing': {'template_pass': True, 'criteria': [True]*6, 'rs_spy': 5.0, 'signal': 'buy',
                               'entry': 100.0, 'stop': 95.0, 'trail': 98.0}},
        }))
    else:
        patches.append(patch('pipeline.build.swing_scan.run_swing_scan', side_effect=RuntimeError('yahoo down')))

    if insider_ok:
        patches.append(patch('pipeline.build.insider_scan.run_insider_scan', return_value={
            'CAVA': {'cluster_buy': True, 'trades': [{'value': 100000, 'transacted': '2026-07-20', 'filed': '2026-07-22'}]},
        }))
    else:
        patches.append(patch('pipeline.build.insider_scan.run_insider_scan', side_effect=RuntimeError('openinsider down')))

    # NOTE: prev_symbols parameterizes what the "previous run" looked like, so
    # tests can control whether build.run()'s diff logic sees something as new.
    patches.append(patch('pipeline.build.jsonbin_client.read_bin', return_value={'symbols': prev_symbols}))
    patches.append(patch('pipeline.build.jsonbin_client.write_bin', return_value=True))
    patches.append(patch('pipeline.build.telegram_notify.send_telegram', return_value=True))
    return patches


def _start_all(patches):
    return [p.start() for p in patches]


def _stop_all(patches):
    for p in patches:
        p.stop()


def test_run_writes_document_with_ok_status_when_everything_succeeds():
    patches = _patch_all()
    _start_all(patches)
    try:
        doc = run()
    finally:
        _stop_all(patches)

    assert doc['meta']['run_status'] == 'ok'
    assert doc['symbols']['CAVA']['swing']['signal'] == 'buy'
    assert doc['symbols']['CAVA']['insider']['cluster_buy'] is True
    assert 'spy_closes' not in doc['market']  # stripped before writing


def test_run_marks_partial_status_when_one_source_fails():
    patches = _patch_all(insider_ok=False)
    _start_all(patches)
    try:
        doc = run()
    finally:
        _stop_all(patches)

    assert doc['meta']['run_status'] == 'partial'
    assert doc['meta']['sources']['insider_scan']['status'] == 'failed'
    assert doc['meta']['sources']['swing_scan']['status'] == 'ok'


def test_run_sends_notification_for_new_buy_signal():
    patches = _patch_all()
    mocks = _start_all(patches)
    try:
        run()
    finally:
        _stop_all(patches)

    send_mock = mocks[-1]
    send_mock.assert_called_once()
    sent_text = send_mock.call_args.args[0]
    assert '1 neues Swing-Signal' in sent_text
    assert DASHBOARD_URL in sent_text


def test_run_skips_notification_when_nothing_new():
    # previous run already had the same buy signal and cluster buy -> nothing new
    prev_symbols = {
        'CAVA': {'swing': {'signal': 'buy'}, 'insider': {'cluster_buy': True}},
    }
    patches = _patch_all(prev_symbols=prev_symbols)
    mocks = _start_all(patches)
    try:
        run()
    finally:
        _stop_all(patches)

    send_mock = mocks[-1]
    send_mock.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.build'`

- [ ] **Step 3: Write `pipeline/build.py`**

```python
"""Orchestrates one full signal-hub run: market ampel -> swing scan ->
insider scan -> diff against the previous JSONBin document -> write ->
notify. Each source is fetched independently; a failure in one source
does not stop the others (see meta.run_status: 'ok' | 'partial' | 'failed')."""
from datetime import datetime, timezone

from pipeline import insider_scan, jsonbin_client, market_ampel, swing_scan, telegram_notify, validate

DASHBOARD_URL = 'https://REPLACE-WITH-GITHUB-USERNAME.github.io/signal-hub/'


def run():
    generated_at = datetime.now(timezone.utc)
    source_statuses = {}
    symbols = {}

    try:
        market = market_ampel.run_market_ampel()
        source_statuses['market_ampel'] = 'ok'
    except Exception as e:
        market = {'spy_regime': 'unknown', 'error': str(e)}
        source_statuses['market_ampel'] = 'failed'

    spy_sma50_ok = market.get('spy_sma50_ok', False)
    spy_closes = market.get('spy_closes')

    try:
        swing_results = swing_scan.run_swing_scan(spy_sma50_ok, spy_closes)
        source_statuses['swing_scan'] = 'ok'
    except Exception:
        swing_results = {}
        source_statuses['swing_scan'] = 'failed'

    for sym, data in swing_results.items():
        symbols.setdefault(sym, {})
        symbols[sym]['price'] = data['price']
        symbols[sym]['swing'] = data['swing']
        symbols[sym]['data_quality'] = data['data_quality']
        if data.get('data_quality_reason'):
            symbols[sym]['data_quality_reason'] = data['data_quality_reason']

    try:
        insider_results = insider_scan.run_insider_scan(swing_scan.UNIVERSE)
        source_statuses['insider_scan'] = 'ok'
    except Exception:
        insider_results = {}
        source_statuses['insider_scan'] = 'failed'

    for sym, data in insider_results.items():
        symbols.setdefault(sym, {})
        symbols[sym]['insider'] = data
        symbols[sym].setdefault('data_quality', 'fresh')

    run_status = validate.determine_run_status(source_statuses)

    market_for_doc = {k: v for k, v in market.items() if k != 'spy_closes'}

    document = {
        'meta': {
            'generated_at': generated_at.isoformat(),
            'run_status': run_status,
            'sources': {
                name: {'status': status, 'ts': generated_at.isoformat()}
                for name, status in source_statuses.items()
            },
        },
        'market': market_for_doc,
        'symbols': symbols,
    }

    try:
        previous = jsonbin_client.read_bin()
    except Exception:
        previous = {}
    prev_symbols = previous.get('symbols', {})

    # `data.get('swing') or {}` (not `data.get('swing', {})`): stale symbols
    # store an explicit `swing: None`, and `.get(key, {})` does NOT substitute
    # the default when the key exists with value None — only `or {}` does.
    new_buy_signals = [
        sym for sym, data in symbols.items()
        if (data.get('swing') or {}).get('signal') == 'buy'
        and (prev_symbols.get(sym, {}).get('swing') or {}).get('signal') != 'buy'
    ]
    new_cluster_buys = [
        sym for sym, data in symbols.items()
        if (data.get('insider') or {}).get('cluster_buy')
        and not (prev_symbols.get(sym, {}).get('insider') or {}).get('cluster_buy')
    ]

    jsonbin_client.write_bin(document)

    message = telegram_notify.build_notification(len(new_buy_signals), len(new_cluster_buys), DASHBOARD_URL)
    if message:
        telegram_notify.send_telegram(message)

    return document
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/build.py tests/test_build.py
git commit -m "feat: add pipeline orchestrator with diff-based notifications"
```

---

## Task 11: Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write `main.py`**

```python
"""Signal Hub pipeline entry point. Run via `python main.py`."""
from pipeline.build import run

if __name__ == '__main__':
    document = run()
    print(f"Run status: {document['meta']['run_status']}")
    print(f"Symbols in document: {len(document['symbols'])}")
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "import main"`
Expected: no output, exit code 0 (confirms no syntax/import errors; this does NOT execute `run()` because of the `__main__` guard)

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add pipeline entry point"
```

---

## Task 12: GitHub Actions Workflow

Reuses TechScreener's cron schedule (already tuned to market hours) and adds `workflow_dispatch` for the dashboard's Refresh button.

**Files:**
- Create: `.github/workflows/signal-hub.yml`

- [ ] **Step 1: Write `.github/workflows/signal-hub.yml`**

```yaml
name: Signal Hub

on:
  schedule:
    # Mo-Fr, UTC-Zeiten (Sommerzeit EDT = UTC-4): 10:00 / 13:30 / 16:45 ET
    - cron: '0 14 * * 1-5'
    - cron: '30 17 * * 1-5'
    - cron: '45 20 * * 1-5'
  workflow_dispatch: {}

jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run signal-hub pipeline
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          JSONBIN_MASTER_KEY: ${{ secrets.JSONBIN_MASTER_KEY }}
          JSONBIN_BIN_ID: ${{ secrets.JSONBIN_BIN_ID }}
        run: python main.py
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/signal-hub.yml'))"`
Expected: no output, exit code 0

(If PyYAML isn't installed locally: `pip install pyyaml` first, or skip this local check — GitHub validates the workflow syntax automatically on push.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/signal-hub.yml
git commit -m "ci: add signal-hub scan workflow (cron + workflow_dispatch)"
```

---

## Task 13: Dashboard — Skeleton, Settings, and JSONBin Read

Single-file PWA at repo root (matches TechScreener's `index.html`-at-root convention for GitHub Pages). This task builds the page shell, a ⚙ Settings modal storing credentials in `localStorage` (never in source — see Implementation Note 4), and the JSONBin read + table render.

**Files:**
- Create: `index.html`

- [ ] **Step 1: Write `index.html`**

```html
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal Hub</title>
<link rel="manifest" href="manifest.json">
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --border: #2a2f3a; --text: #e6e8eb;
    --muted: #8b93a3; --green: #3ecf8e; --red: #ef5b5b; --amber: #e0a52c; --accent: #4f8ef7;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, Segoe UI, sans-serif; }
  header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
  header h1 { font-size: 18px; margin: 0; }
  header .actions { display: flex; gap: 8px; }
  button { background: var(--panel); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px; cursor: pointer; font-size: 14px; }
  button:hover { border-color: var(--accent); }
  button:disabled { opacity: 0.5; cursor: default; }
  #freshness { padding: 8px 16px; font-size: 13px; color: var(--muted); border-bottom: 1px solid var(--border); }
  #freshness.warn { color: var(--amber); }
  #freshness.fail { color: var(--red); }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border); }
  th { cursor: pointer; color: var(--muted); font-weight: 600; user-select: none; }
  tr:hover { background: var(--panel); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
  .badge.pass { background: rgba(62,207,142,0.15); color: var(--green); }
  .badge.fail { background: rgba(239,91,91,0.15); color: var(--red); }
  .badge.insider { background: rgba(224,165,44,0.15); color: var(--amber); }
  dialog { background: var(--panel); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 16px; max-width: 420px; }
  dialog label { display: block; margin-top: 10px; font-size: 13px; color: var(--muted); }
  dialog input { width: 100%; padding: 8px; margin-top: 4px; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 6px; }
  dialog .dialog-actions { margin-top: 16px; display: flex; justify-content: flex-end; gap: 8px; }
  #empty-state { padding: 40px; text-align: center; color: var(--muted); }
</style>
</head>
<body>
<header>
  <h1>Signal Hub</h1>
  <div class="actions">
    <button id="refresh-btn">Refresh</button>
    <button id="settings-btn">Einstellungen</button>
  </div>
</header>
<div id="freshness">Lade...</div>
<div id="table-container">
  <table id="signal-table">
    <thead>
      <tr>
        <th data-sort="sym">Symbol</th>
        <th data-sort="price">Preis</th>
        <th data-sort="template">Template</th>
        <th data-sort="signal">Signal</th>
        <th data-sort="insider">Insider</th>
        <th data-sort="rs">RS vs SPY</th>
      </tr>
    </thead>
    <tbody id="table-body"></tbody>
  </table>
  <div id="empty-state" style="display:none;">Keine Daten. Einstellungen pruefen (JSONBin Bin ID + Key).</div>
</div>

<dialog id="settings-dialog">
  <h2 style="margin-top:0;">Einstellungen</h2>
  <label>JSONBin Bin ID
    <input id="cfg-bin-id" type="text" placeholder="6512...abc">
  </label>
  <label>JSONBin Read/Master Key
    <input id="cfg-jsonbin-key" type="password" placeholder="$2a$10$...">
  </label>
  <label>GitHub Repo (owner/name)
    <input id="cfg-github-repo" type="text" placeholder="DHachtel/signal-hub">
  </label>
  <label>GitHub PAT (nur "Actions: Read and write" auf diesem Repo)
    <input id="cfg-github-pat" type="password" placeholder="github_pat_...">
  </label>
  <div class="dialog-actions">
    <button id="settings-cancel">Abbrechen</button>
    <button id="settings-save">Speichern</button>
  </div>
</dialog>

<script>
const CFG_KEYS = ['cfg-bin-id', 'cfg-jsonbin-key', 'cfg-github-repo', 'cfg-github-pat'];
const STORAGE_PREFIX = 'signalhub_';

function loadConfig() {
  const cfg = {};
  for (const key of CFG_KEYS) cfg[key] = localStorage.getItem(STORAGE_PREFIX + key) || '';
  return cfg;
}

function saveConfig() {
  for (const key of CFG_KEYS) {
    const el = document.getElementById(key);
    localStorage.setItem(STORAGE_PREFIX + key, el.value.trim());
  }
}

function hasMinimalConfig() {
  const cfg = loadConfig();
  return !!(cfg['cfg-bin-id'] && cfg['cfg-jsonbin-key']);
}

async function fetchDocument() {
  const cfg = loadConfig();
  const url = `https://api.jsonbin.io/v3/b/${cfg['cfg-bin-id']}/latest`;
  const resp = await fetch(url, { headers: { 'X-Master-Key': cfg['cfg-jsonbin-key'] } });
  if (!resp.ok) throw new Error(`JSONBin ${resp.status}`);
  const body = await resp.json();
  return body.record;
}

function fmtAge(generatedAtIso) {
  const diffMs = Date.now() - new Date(generatedAtIso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `vor ${mins} Min`;
  const hours = Math.round(mins / 60);
  return `vor ${hours} Std`;
}

function renderFreshness(doc) {
  const el = document.getElementById('freshness');
  if (!doc || !doc.meta) {
    el.textContent = 'Keine Daten geladen.';
    el.className = 'fail';
    return;
  }
  const age = fmtAge(doc.meta.generated_at);
  el.textContent = `Zuletzt aktualisiert ${age} — Status: ${doc.meta.run_status}`;
  el.className = doc.meta.run_status === 'ok' ? '' : (doc.meta.run_status === 'partial' ? 'warn' : 'fail');
}

function renderTable(doc) {
  const tbody = document.getElementById('table-body');
  const emptyState = document.getElementById('empty-state');
  tbody.innerHTML = '';

  const symbols = (doc && doc.symbols) ? doc.symbols : {};
  const rows = Object.entries(symbols);
  if (rows.length === 0) {
    emptyState.style.display = 'block';
    return;
  }
  emptyState.style.display = 'none';

  for (const [sym, data] of rows) {
    const tr = document.createElement('tr');
    const swing = data.swing || {};
    const insider = data.insider || {};
    const templateBadge = swing.template_pass
      ? '<span class="badge pass">pass</span>' : '<span class="badge fail">fail</span>';
    const signalText = swing.signal === 'buy' ? `buy @ ${swing.entry ?? '-'}` : '–';
    const insiderBadge = insider.cluster_buy ? '<span class="badge insider">Cluster-Buy</span>' : '—';
    const qualityNote = data.data_quality === 'stale'
      ? ` <span title="${data.data_quality_reason || ''}">⚠️</span>` : '';

    tr.innerHTML = `
      <td>${sym}${qualityNote}</td>
      <td>${data.price != null ? '$' + data.price.toFixed(2) : '–'}</td>
      <td>${templateBadge}</td>
      <td>${signalText}</td>
      <td>${insiderBadge}</td>
      <td>${swing.rs_spy != null ? swing.rs_spy.toFixed(1) + '%' : '–'}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function loadAndRender() {
  if (!hasMinimalConfig()) {
    document.getElementById('freshness').textContent = 'Bitte Einstellungen konfigurieren.';
    document.getElementById('empty-state').style.display = 'block';
    return;
  }
  try {
    const doc = await fetchDocument();
    renderFreshness(doc);
    renderTable(doc);
  } catch (e) {
    document.getElementById('freshness').textContent = `Fehler beim Laden: ${e.message}`;
    document.getElementById('freshness').className = 'fail';
  }
}

document.getElementById('settings-btn').addEventListener('click', () => {
  const cfg = loadConfig();
  for (const key of CFG_KEYS) document.getElementById(key).value = cfg[key];
  document.getElementById('settings-dialog').showModal();
});

document.getElementById('settings-cancel').addEventListener('click', () => {
  document.getElementById('settings-dialog').close();
});

document.getElementById('settings-save').addEventListener('click', () => {
  saveConfig();
  document.getElementById('settings-dialog').close();
  loadAndRender();
});

loadAndRender();
</script>
</body>
</html>
```

- [ ] **Step 2: Manual verification (no automated test — this is a static page with no local dev server yet)**

Open `index.html` directly in a browser (`file://` URL). Expected: page renders with header, "Bitte Einstellungen konfigurieren." message, and empty-state text visible (since no JSONBin credentials are stored yet). No console errors.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add dashboard skeleton with settings modal and JSONBin read"
```

---

## Task 14: Dashboard — Refresh Button (workflow_dispatch + polling)

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add the refresh logic to the `<script>` block in `index.html`**, before the final `loadAndRender();` call:

```html
<script>
// ... (existing code from Task 13 stays above this point) ...

async function triggerWorkflowDispatch() {
  const cfg = loadConfig();
  const [owner, repo] = (cfg['cfg-github-repo'] || '').split('/');
  if (!owner || !repo || !cfg['cfg-github-pat']) {
    throw new Error('GitHub Repo oder PAT fehlt in den Einstellungen');
  }
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/signal-hub.yml/dispatches`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${cfg['cfg-github-pat']}`,
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ref: 'main' }),
  });
  if (resp.status !== 204) {
    throw new Error(`GitHub API ${resp.status}`);
  }
}

async function pollForCompletion(triggeredAt) {
  const cfg = loadConfig();
  const [owner, repo] = (cfg['cfg-github-repo'] || '').split('/');
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/signal-hub.yml/runs?per_page=5`;
  const maxAttempts = 12; // 12 * 15s = 3 minutes
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await new Promise(r => setTimeout(r, 15000));
    try {
      const resp = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${cfg['cfg-github-pat']}`,
          'Accept': 'application/vnd.github+json',
        },
      });
      if (!resp.ok) continue;
      const body = await resp.json();
      const freshRun = (body.workflow_runs || []).find(r =>
        new Date(r.created_at).getTime() >= triggeredAt && r.status === 'completed'
      );
      if (freshRun) return true;
    } catch (e) {
      // transient network error while polling — keep trying until maxAttempts
    }
  }
  return false;
}

document.getElementById('refresh-btn').addEventListener('click', async () => {
  const btn = document.getElementById('refresh-btn');
  const freshnessEl = document.getElementById('freshness');
  btn.disabled = true;
  const originalText = btn.textContent;
  try {
    btn.textContent = 'Starte Scan...';
    const triggeredAt = Date.now();
    await triggerWorkflowDispatch();
    btn.textContent = 'Scan laeuft (~2-3 Min)...';
    freshnessEl.textContent = 'Scan laeuft, bitte warten...';
    const completed = await pollForCompletion(triggeredAt);
    if (completed) {
      btn.textContent = 'Fertig, lade neu...';
      await loadAndRender();
    } else {
      freshnessEl.textContent = 'Scan laeuft laenger als erwartet — spaeter erneut pruefen.';
      freshnessEl.className = 'warn';
    }
  } catch (e) {
    freshnessEl.textContent = `Refresh fehlgeschlagen: ${e.message}`;
    freshnessEl.className = 'fail';
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});

loadAndRender();
</script>
```

- [ ] **Step 2: Manual verification**

Open `index.html` in a browser with no GitHub settings configured, click "Refresh". Expected: button briefly shows "Starte Scan...", then the freshness banner shows an error mentioning "GitHub Repo oder PAT fehlt", and the button re-enables. This confirms the error path works before real credentials exist (real end-to-end verification happens in Task 18 once the repo is pushed and Pages is live).

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add refresh button with workflow_dispatch trigger and polling"
```

---

## Task 15: PWA Manifest & Service Worker

Makes the dashboard installable on a phone home screen, per the design's "installierbar als PWA am Handy" requirement.

**Files:**
- Create: `manifest.json`
- Create: `sw.js`
- Modify: `index.html`

- [ ] **Step 1: Write `manifest.json`**

```json
{
  "name": "Signal Hub",
  "short_name": "SignalHub",
  "start_url": "./index.html",
  "display": "standalone",
  "background_color": "#0f1115",
  "theme_color": "#0f1115",
  "icons": [
    {
      "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='16' fill='%234f8ef7'/%3E%3Ctext x='50' y='62' font-size='40' text-anchor='middle' fill='white' font-family='sans-serif'%3ESH%3C/text%3E%3C/svg%3E",
      "sizes": "192x192",
      "type": "image/svg+xml"
    }
  ]
}
```

- [ ] **Step 2: Write `sw.js`** (minimal cache-first service worker — only what's needed for installability, no offline data caching since the whole point is fresh data)

```javascript
const CACHE_NAME = 'signal-hub-shell-v1';
const SHELL_FILES = ['./index.html', './manifest.json'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Only serve the app shell from cache; JSONBin/GitHub API calls always go to the network.
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
```

- [ ] **Step 3: Register the service worker** — add before the closing `</script>` tag in `index.html` (after `loadAndRender();`):

```html
<script>
// ... existing script content ...

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./sw.js').catch(() => {
    // Registration failure is non-fatal — the page still works, just not installable.
  });
}
</script>
```

- [ ] **Step 4: Manual verification**

Serve the directory locally (`python -m http.server 8000`) and open `http://localhost:8000/index.html` in Chrome. Expected: DevTools → Application → Manifest shows "Signal Hub" with no errors; Application → Service Workers shows `sw.js` registered and activated.

- [ ] **Step 5: Commit**

```bash
git add manifest.json sw.js index.html
git commit -m "feat: add PWA manifest and service worker for installability"
```

---

## Task 16: GitHub Pages Setup (manual, no code)

**Files:** none — repository settings only.

- [ ] **Step 1:** Push the repo to GitHub (create a **public** repository — GitHub Pages on the free tier requires a public repo; this is why data privacy is handled at the JSONBin layer, not by making the repo private).

```bash
git remote add origin https://github.com/<your-username>/signal-hub.git
git push -u origin main
```

- [ ] **Step 2:** In the GitHub repo, go to **Settings → Pages**. Under "Build and deployment", set **Source: Deploy from a branch**, **Branch: main**, **Folder: / (root)**. Save.

- [ ] **Step 3:** Wait ~1 minute, then note the published URL shown on the Pages settings screen (format: `https://<username>.github.io/signal-hub/`).

- [ ] **Step 4:** Update `pipeline/build.py`'s `DASHBOARD_URL` constant with the real URL from Step 3.

```python
DASHBOARD_URL = 'https://<username>.github.io/signal-hub/'
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/build.py
git commit -m "chore: set real GitHub Pages dashboard URL"
git push
```

---

## Task 17: README — Full Setup Instructions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` with complete setup instructions**

```markdown
# Signal Hub

Konsolidierter Swing-Trading-Signal-Hub: Minervini Trend Template + EMA21 Pullback
(portiert aus TechScreener), Insider-Trading-Aktivitaet (openinsider.com) und
Markt-Ampel (SPY vs. 50-Tage-SMA) in einem taeglich per Knopfdruck aktualisierbaren
Dashboard. Kostenlos: GitHub Actions + JSONBin.io + GitHub Pages.

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

### 4. GitHub Pages aktivieren

Siehe Task 16 im Implementierungsplan — Settings → Pages → Deploy from branch → main → / (root).

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

1. `https://<username>.github.io/signal-hub/` oeffnen.
2. ⚙ Einstellungen: JSONBin Bin ID, JSONBin Master Key, GitHub Repo
   (`<username>/signal-hub`), GitHub PAT aus Schritt 5 eintragen. Speichern.
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add complete setup instructions"
```

---

## Task 18: End-to-End Verification

No new files — this task confirms the whole system works together before considering the project done.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass (should be ~40+ tests across Tasks 2–10).

- [ ] **Step 2: Run the pipeline locally against real credentials**

With `JSONBIN_MASTER_KEY`, `JSONBIN_BIN_ID` (and optionally the Telegram vars) exported as environment variables:

```bash
python main.py
```

Expected: prints `Run status: ok` (or `partial` if e.g. openinsider.com is temporarily unreachable) and a nonzero symbol count. Check the JSONBin dashboard directly to confirm the document was written.

- [ ] **Step 3: Verify the live dashboard**

Open the GitHub Pages URL, configure ⚙ Settings with real JSONBin + GitHub values, confirm:
- Freshness banner shows a recent timestamp and `run_status`.
- Table lists symbols with Template/Signal/Insider columns populated.
- Clicking "Refresh" triggers a new Actions run (visible under the repo's Actions tab) and the dashboard reloads with updated data after completion.

- [ ] **Step 4: Verify a full cron cycle**

Wait for (or manually confirm via Actions tab) one of the three scheduled runs to complete successfully without manual intervention.

- [ ] **Step 5: Final commit** (only if Steps 1-4 required fixes; otherwise this task produces no diff)

```bash
git add -A
git commit -m "fix: address issues found during end-to-end verification"
```

---

## Self-Review Notes

- **Spec coverage:** every section of the design spec maps to a task — architecture (Tasks 1, 10–12), data quality (Task 3), data model (Task 10's document shape), dashboard (Tasks 13–15), consolidation/notification behavior (Tasks 9–10), setup/deployment (Tasks 16–17), verification (Task 18).
- **Deviations from the spec are documented explicitly** in "Implementation Notes" at the top, with rationale, rather than silently diverging — the parity-test approach and the localStorage-vs-hardcoded-secret decision both need the user's awareness since they change how "done" is verified and how credentials are handled.
- **Type/name consistency check:** `data_quality` values (`'fresh'`/`'stale'`) are used identically in `validate.py`, `swing_scan.py`, `build.py`, and `index.html`. The JSONBin document's `symbols[sym]` shape (`price`, `swing`, `insider`, `data_quality`, `data_quality_reason`) is produced in `build.py` and consumed identically in `index.html`'s `renderTable`. `swing.signal` is `'buy'` or `'-'` consistently in `swing_scan.py`, `build.py`'s diff logic, and the dashboard.
