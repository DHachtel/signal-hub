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
        # period='1y' returns only ~251 daily bars (just under the 252-bar
        # minimum validate.validate_symbol requires for the Trend Template),
        # which made every symbol fail as 'stale'. '2y' gives comfortable
        # margin — TechScreener's own JS side hit the identical issue and
        # fixed it the same way (6mo -> 2y for Trend Template SMA200).
        hist = yf.Ticker(sym).history(period='2y', interval='1d', auto_adjust=True)
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
