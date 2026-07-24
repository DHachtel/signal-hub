from unittest.mock import patch, Mock
import pytest
from pipeline import jsonbin_client


def test_read_bin_returns_record(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', 'testkey')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', 'testbin')
    resp = Mock(status_code=200)
    resp.json.return_value = {'record': {'foo': 'bar'}}
    resp.raise_for_status = Mock()
    with patch('pipeline.jsonbin_client.requests.get', return_value=resp):
        result = jsonbin_client.read_bin()
    assert result == {'foo': 'bar'}


def test_read_bin_raises_without_credentials(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', '')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', '')
    with pytest.raises(RuntimeError):
        jsonbin_client.read_bin()


def test_write_bin_sends_put_with_document(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', 'testkey')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', 'testbin')
    resp = Mock(status_code=200)
    resp.raise_for_status = Mock()
    with patch('pipeline.jsonbin_client.requests.put', return_value=resp) as mock_put:
        result = jsonbin_client.write_bin({'foo': 'bar'})
    assert result is True
    mock_put.assert_called_once()
    assert mock_put.call_args.kwargs['json'] == {'foo': 'bar'}


def test_write_bin_raises_without_credentials(monkeypatch):
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_KEY', '')
    monkeypatch.setattr(jsonbin_client, 'JSONBIN_BIN', '')
    with pytest.raises(RuntimeError):
        jsonbin_client.write_bin({'foo': 'bar'})
