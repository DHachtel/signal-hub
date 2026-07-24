from pipeline.telegram_notify import build_notification


def test_build_notification_none_when_nothing_new():
    assert build_notification(0, 0, 'https://example.com') is None


def test_build_notification_singular_signal_wording():
    msg = build_notification(1, 0, 'https://example.com')
    assert '1 neues Swing-Signal' in msg
    assert 'Signale' not in msg


def test_build_notification_plural_signal_wording():
    msg = build_notification(3, 0, 'https://example.com')
    assert '3 neue Swing-Signale' in msg


def test_build_notification_includes_insider_count_and_link():
    msg = build_notification(0, 1, 'https://example.com')
    assert '1 neuer Insider-Cluster-Buy' in msg
    assert 'https://example.com' in msg


def test_build_notification_plural_insider_wording():
    msg = build_notification(0, 2, 'https://example.com')
    assert '2 neue Insider-Cluster-Buys' in msg
