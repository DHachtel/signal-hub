"""Telegram notification: a link, not a report. The actual data lives in the
dashboard — Telegram's only job is to say "something changed, go look"."""
import os

import requests

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')


def build_notification(new_signals_count, new_insider_count, dashboard_url):
    """Build the notification text, or return None if there's nothing new
    to report (caller should skip sending in that case)."""
    if new_signals_count == 0 and new_insider_count == 0:
        return None

    parts = ['\U0001f514 <b>Signal Hub Update</b>']

    if new_signals_count == 1:
        parts.append('1 neues Swing-Signal')
    elif new_signals_count > 1:
        parts.append(f'{new_signals_count} neue Swing-Signale')

    if new_insider_count == 1:
        parts.append('1 neuer Insider-Cluster-Buy')
    elif new_insider_count > 1:
        parts.append(f'{new_insider_count} neue Insider-Cluster-Buys')

    parts.append(f'→ {dashboard_url}')
    return '\n'.join(parts)


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print('TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt')
        return False
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    resp = requests.post(url, json=payload, timeout=10)
    return resp.status_code == 200
