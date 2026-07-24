from unittest.mock import patch, Mock
from pipeline.insider_scan import (
    parse_value,
    fetch_openinsider_table,
    fetch_universe_purchases,
    fetch_cluster_buys_outside_universe,
    run_insider_scan,
)

PURCHASES_HTML = """
<html><body>
<table class="tinytable">
<tr><th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Company Name</th>
<th>Insider Name</th><th>Title</th><th>Trade Type</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>ΔOwn</th><th>Value</th><th>1d</th><th>1w</th><th>1m</th><th>6m</th></tr>
<tr><td>M</td><td>2026-07-23 21:22:32</td><td>2026-07-21</td><td>CAVA</td>
<td>Cava Group, Inc.</td><td>Jane Doe</td><td>CEO</td><td>P - Purchase</td>
<td>$9.76</td><td>+10,000</td><td>50,000</td><td>+25%</td><td>+$97,600</td>
<td></td><td></td><td></td><td></td></tr>
<tr><td>A</td><td>2026-07-23 20:00:00</td><td>2026-07-20</td><td>CAVA</td>
<td>Cava Group, Inc.</td><td>John Roe</td><td>Dir</td><td>P - Purchase</td>
<td>$9.50</td><td>+500</td><td>10,000</td><td>+5%</td><td>+$4,750</td>
<td></td><td></td><td></td><td></td></tr>
<tr><td></td><td>2026-07-23 19:00:00</td><td>2026-07-20</td><td>XYZ</td>
<td>Some Corp</td><td>John Roe</td><td>Dir</td><td>S - Sale</td>
<td>$5.00</td><td>-1,000</td><td>1,000</td><td>-10%</td><td>-$5,000</td>
<td></td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""

CLUSTER_HTML = """
<html><body>
<table class="tinytable">
<tr><th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Company Name</th>
<th>Industry</th><th>Ins</th><th>Trade Type</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>ΔOwn</th><th>Value</th><th>1d</th><th>1w</th><th>1m</th><th>6m</th></tr>
<tr><td>M</td><td>2026-07-23 18:47:22</td><td>2026-07-22</td><td>BYRN</td>
<td>Byrna Technologies Inc.</td><td>Misc. Electrical</td><td>3</td><td>P - Purchase</td>
<td>$3.48</td><td>+72,789</td><td>377,652</td><td>+24%</td><td>+$253,222</td>
<td></td><td></td><td></td><td></td></tr>
<tr><td>D</td><td>2026-07-23 16:24:22</td><td>2026-07-22</td><td>ONE</td>
<td>Solo Insider Corp</td><td>Banks</td><td>1</td><td>P - Purchase</td>
<td>$11.95</td><td>+5,000</td><td>10,000</td><td>+75%</td><td>+$59,750</td>
<td></td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""


def _mock_get(html):
    resp = Mock(status_code=200, text=html)
    resp.raise_for_status = Mock()
    return resp


def test_parse_value_handles_currency_formatting():
    assert parse_value('+$2,583,314') == 2583314.0
    assert parse_value('-$1,380,764') == -1380764.0
    assert parse_value('') is None
    assert parse_value(None) is None


def test_fetch_openinsider_table_parses_rows_into_dicts():
    with patch('pipeline.insider_scan.requests.get', return_value=_mock_get(PURCHASES_HTML)):
        rows = fetch_openinsider_table('http://openinsider.com/latest-insider-purchases-25k')
    assert len(rows) == 3
    assert rows[0]['Ticker'] == 'CAVA'
    assert rows[0]['Trade Type'] == 'P - Purchase'


def test_fetch_universe_purchases_filters_universe_type_and_min_value():
    with patch('pipeline.insider_scan.requests.get', return_value=_mock_get(PURCHASES_HTML)):
        trades = fetch_universe_purchases(['CAVA', 'TSLA'])
    # XYZ excluded (not in universe), sale rows excluded even if they were in universe
    assert {t['sym'] for t in trades} == {'CAVA'}
    assert len(trades) == 2
    assert all(t['value'] > 0 for t in trades)


def test_fetch_cluster_buys_outside_universe_requires_min_insiders():
    with patch('pipeline.insider_scan.requests.get', return_value=_mock_get(CLUSTER_HTML)):
        clusters = fetch_cluster_buys_outside_universe(['CAVA'], min_insiders=2)
    syms = {c['sym'] for c in clusters}
    assert 'BYRN' in syms   # 3 insiders, passes
    assert 'ONE' not in syms  # only 1 insider, filtered out


def test_run_insider_scan_merges_universe_and_cluster_results():
    def side_effect(url, headers=None, timeout=None):
        if 'cluster' in url:
            return _mock_get(CLUSTER_HTML)
        return _mock_get(PURCHASES_HTML)

    with patch('pipeline.insider_scan.requests.get', side_effect=side_effect):
        result = run_insider_scan(['CAVA'])

    assert 'CAVA' in result
    assert result['CAVA']['cluster_buy'] is True  # 2 distinct insiders in PURCHASES_HTML
    assert 'BYRN' in result
    assert result['BYRN']['cluster_buy'] is True
