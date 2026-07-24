"""Orchestrates one full signal-hub run: market ampel -> swing scan ->
insider scan -> diff against the previous JSONBin document -> write ->
notify. Each source is fetched independently; a failure in one source
does not stop the others (see meta.run_status: 'ok' | 'partial' | 'failed')."""
from datetime import datetime, timezone

from pipeline import insider_scan, jsonbin_client, market_ampel, swing_scan, telegram_notify, validate

DASHBOARD_URL = 'https://REPLACE-WITH-GITHUB-USERNAME.github.io/signal-hub/'


def run():
    generated_at = datetime.now(timezone.utc)
    source_statuses = {}
    symbols = {}

    try:
        market = market_ampel.run_market_ampel()
        source_statuses['market_ampel'] = 'ok'
    except Exception as e:
        market = {'spy_regime': 'unknown', 'error': str(e)}
        source_statuses['market_ampel'] = 'failed'

    spy_sma50_ok = market.get('spy_sma50_ok', False)
    spy_closes = market.get('spy_closes')

    try:
        swing_results = swing_scan.run_swing_scan(spy_sma50_ok, spy_closes)
        source_statuses['swing_scan'] = 'ok'
    except Exception:
        swing_results = {}
        source_statuses['swing_scan'] = 'failed'

    for sym, data in swing_results.items():
        symbols.setdefault(sym, {})
        symbols[sym]['price'] = data['price']
        symbols[sym]['swing'] = data['swing']
        symbols[sym]['data_quality'] = data['data_quality']
        if data.get('data_quality_reason'):
            symbols[sym]['data_quality_reason'] = data['data_quality_reason']

    try:
        insider_results = insider_scan.run_insider_scan(swing_scan.UNIVERSE)
        source_statuses['insider_scan'] = 'ok'
    except Exception:
        insider_results = {}
        source_statuses['insider_scan'] = 'failed'

    for sym, data in insider_results.items():
        symbols.setdefault(sym, {})
        symbols[sym]['insider'] = data
        symbols[sym].setdefault('data_quality', 'fresh')

    run_status = validate.determine_run_status(source_statuses)

    market_for_doc = {k: v for k, v in market.items() if k != 'spy_closes'}

    document = {
        'meta': {
            'generated_at': generated_at.isoformat(),
            'run_status': run_status,
            'sources': {
                name: {'status': status, 'ts': generated_at.isoformat()}
                for name, status in source_statuses.items()
            },
        },
        'market': market_for_doc,
        'symbols': symbols,
    }

    try:
        previous = jsonbin_client.read_bin()
    except Exception:
        previous = {}
    prev_symbols = previous.get('symbols', {})

    new_buy_signals = [
        sym for sym, data in symbols.items()
        if (data.get('swing') or {}).get('signal') == 'buy'
        and (prev_symbols.get(sym, {}).get('swing') or {}).get('signal') != 'buy'
    ]
    new_cluster_buys = [
        sym for sym, data in symbols.items()
        if (data.get('insider') or {}).get('cluster_buy')
        and not (prev_symbols.get(sym, {}).get('insider') or {}).get('cluster_buy')
    ]

    jsonbin_client.write_bin(document)

    message = telegram_notify.build_notification(len(new_buy_signals), len(new_cluster_buys), DASHBOARD_URL)
    if message:
        telegram_notify.send_telegram(message)

    return document
