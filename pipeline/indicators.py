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
