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
