"""Data quality gate for the swing scan. Runs per-symbol before a result
is written into the JSONBin document, and aggregates per-source run
status into an overall run_status for meta.run_status.
"""
from datetime import date, datetime, timezone

MAX_DATA_AGE_DAYS = 4  # covers a normal weekend + one holiday; daily EOD bars only
MIN_TREND_TEMPLATE_BARS = 252


def validate_symbol(last_close_date, closes):
    """Validate a symbol's daily close history before it's used for the swing scan.

    Args:
        last_close_date: date of the most recent bar, or None if unknown.
        closes: list of daily close prices (most recent last).

    Returns:
        (quality, reason) where quality is 'fresh' or 'stale', and reason is
        a human-readable string when quality == 'stale', else None.
    """
    if not closes or len(closes) < MIN_TREND_TEMPLATE_BARS:
        n = len(closes) if closes else 0
        return 'stale', f'Nur {n} Handelstage verfuegbar (<{MIN_TREND_TEMPLATE_BARS})'

    if any(c is None for c in closes[-MIN_TREND_TEMPLATE_BARS:]):
        return 'stale', 'Luecken in den letzten 252 Kursdaten'

    if last_close_date is None:
        return 'stale', 'Kein Datum fuer den letzten Kurs bekannt'

    age_days = (datetime.now(timezone.utc).date() - last_close_date).days
    if age_days > MAX_DATA_AGE_DAYS:
        return 'stale', f'Kursdaten {age_days} Tage alt (Schwellwert {MAX_DATA_AGE_DAYS})'

    return 'fresh', None


def determine_run_status(source_statuses):
    """Aggregate per-source 'ok'/'failed' statuses into an overall run status.

    Args:
        source_statuses: dict of {source_name: 'ok' | 'failed'}.

    Returns:
        'ok' if every source succeeded, 'failed' if every source failed,
        else 'partial'.
    """
    values = list(source_statuses.values())
    if values and all(v == 'ok' for v in values):
        return 'ok'
    if values and all(v == 'failed' for v in values):
        return 'failed'
    return 'partial'
