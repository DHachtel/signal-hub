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
