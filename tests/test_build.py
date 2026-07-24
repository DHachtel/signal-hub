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


def test_run_handles_stale_symbol_with_none_swing_without_crashing():
    # A symbol with stale/insufficient data has swing=None (see swing_scan.scan_symbol).
    # The diff logic must not crash on that, for both the current and the previous document.
    prev_symbols = {
        'ACME': {'swing': None, 'insider': {'cluster_buy': False}},
    }
    patches = _patch_all(prev_symbols=prev_symbols)
    # Override the default swing_scan mock with one that includes a stale (swing=None) symbol.
    patches[1] = patch('pipeline.build.swing_scan.run_swing_scan', return_value={
        'ACME': {'price': None, 'data_quality': 'stale', 'swing': None},
        'CAVA': {'price': 100.0, 'data_quality': 'fresh',
                 'swing': {'template_pass': True, 'criteria': [True] * 6, 'rs_spy': 5.0, 'signal': 'buy',
                           'entry': 100.0, 'stop': 95.0, 'trail': 98.0}},
    })
    _start_all(patches)
    try:
        doc = run()
    finally:
        _stop_all(patches)

    assert doc['symbols']['ACME']['swing'] is None
    assert doc['symbols']['CAVA']['swing']['signal'] == 'buy'


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
