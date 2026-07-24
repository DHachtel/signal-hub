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
