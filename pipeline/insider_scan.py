"""Insider trading scan via openinsider.com's bulk list pages.
Verified table structure (2026-07-24, table.tinytable class, 17 columns):
Filing Date, Trade Date, Ticker, Company Name, [Insider Name|Industry],
[Title|Ins], Trade Type, Price, Qty, Owned, DeltaOwn, Value, 1d, 1w, 1m, 6m.
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (SignalHub Bot)'}
PURCHASES_URL = 'http://openinsider.com/latest-insider-purchases-25k'
CLUSTER_BUYS_URL = 'http://openinsider.com/latest-cluster-buys'
MIN_TRADE_VALUE = 50_000


def parse_value(text):
    """Parse a Value cell like '+$2,583,314' into a float, or None if unparseable."""
    if not text:
        return None
    cleaned = text.replace('$', '').replace(',', '').replace('+', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_openinsider_table(url):
    """Fetch an openinsider.com list page and return rows as header-keyed dicts."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table', class_='tinytable')
    if table is None:
        return []
    rows = table.find_all('tr')
    if not rows:
        return []
    headers = [th.text.strip() for th in rows[0].find_all('th')]
    result = []
    for row in rows[1:]:
        cells = row.find_all('td')
        if len(cells) != len(headers):
            continue
        values = [c.text.strip() for c in cells]
        result.append(dict(zip(headers, values)))
    return result


def fetch_universe_purchases(universe):
    """Latest insider purchases filtered to symbols in `universe`, purchases only.

    No MIN_TRADE_VALUE filter here: `universe` is already a curated ~80-symbol
    watchlist, so any purchase size in a tracked symbol is worth surfacing.
    (MIN_TRADE_VALUE noise-filtering is applied in
    fetch_cluster_buys_outside_universe, which scans the unfiltered market-wide
    cluster-buys list.)"""
    universe_set = {s.upper() for s in universe}
    trades = []
    for row in fetch_openinsider_table(PURCHASES_URL):
        ticker = row.get('Ticker', '').upper()
        if ticker not in universe_set:
            continue
        if not row.get('Trade Type', '').startswith('P'):
            continue
        value = parse_value(row.get('Value', ''))
        if value is None:
            continue
        trades.append({
            'sym': ticker,
            'insider': row.get('Insider Name', ''),
            'role': row.get('Title', ''),
            'value': abs(value),
            'transacted': row.get('Trade Date', ''),
            'filed': row.get('Filing Date', ''),
        })
    return trades


def fetch_cluster_buys_outside_universe(universe, min_insiders=2):
    """Latest cluster buys for symbols NOT in `universe`, requiring at least
    `min_insiders` distinct buyers and MIN_TRADE_VALUE per trade."""
    universe_set = {s.upper() for s in universe}
    grouped = {}
    for row in fetch_openinsider_table(CLUSTER_BUYS_URL):
        ticker = row.get('Ticker', '').upper()
        if ticker in universe_set:
            continue
        try:
            ins_count = int(row.get('Ins', '0') or '0')
        except ValueError:
            ins_count = 0
        if ins_count < min_insiders:
            continue
        value = parse_value(row.get('Value', ''))
        if value is None or abs(value) < MIN_TRADE_VALUE:
            continue
        entry = grouped.setdefault(ticker, {'sym': ticker, 'insider_count': ins_count, 'trades': []})
        entry['trades'].append({
            'value': abs(value),
            'transacted': row.get('Trade Date', ''),
            'filed': row.get('Filing Date', ''),
        })
    return list(grouped.values())


def _group_universe_trades(trades):
    grouped = {}
    for t in trades:
        sym = t['sym']
        entry = grouped.setdefault(sym, {'trades': []})
        entry['trades'].append({k: v for k, v in t.items() if k != 'sym'})
    for sym, data in grouped.items():
        distinct_insiders = {tr['insider'] for tr in data['trades'] if tr.get('insider')}
        data['cluster_buy'] = len(distinct_insiders) >= 2
        data['insider_count'] = len(distinct_insiders)
    return grouped


def run_insider_scan(universe):
    """Full insider scan: universe purchases + cluster buys outside universe.
    Returns {sym: {cluster_buy: bool, trades: [...], insider_count: int|None}}
    ready for the symbols section of the JSONBin document.

    The two source pages are fetched independently: a failure on one
    (network error, site layout change, rate limit) does not discard
    results already fetched from the other — it's logged and treated as
    an empty result for that source instead.
    """
    try:
        universe_trades = fetch_universe_purchases(universe)
    except Exception as e:
        print(f'insider_scan: fetch_universe_purchases failed: {e}')
        universe_trades = []
    result = _group_universe_trades(universe_trades)

    try:
        cluster_entries = fetch_cluster_buys_outside_universe(universe)
    except Exception as e:
        print(f'insider_scan: fetch_cluster_buys_outside_universe failed: {e}')
        cluster_entries = []

    for entry in cluster_entries:
        result[entry['sym']] = {
            'cluster_buy': True,
            'insider_count': entry['insider_count'],
            'trades': entry['trades'],
        }

    return result
