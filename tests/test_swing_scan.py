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
