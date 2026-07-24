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
