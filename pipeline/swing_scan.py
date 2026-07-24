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
