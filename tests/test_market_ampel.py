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
