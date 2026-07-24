"""JSONBin.io v3 client. Same read/write pattern as
TechScreener/github-alerts/screener.py's read_positions_from_jsonbin /
write_candidates_to_jsonbin, generalized to a whole-document read/write.
"""
import os

import requests

JSONBIN_KEY = os.environ.get('JSONBIN_MASTER_KEY', '')
JSONBIN_BIN = os.environ.get('JSONBIN_BIN_ID', '')
BASE_URL = 'https://api.jsonbin.io/v3/b'


def read_bin():
    """Read the current JSONBin document. Raises RuntimeError if credentials
    are missing, or requests.HTTPError on a non-2xx response."""
    if not JSONBIN_KEY or not JSONBIN_BIN:
        raise RuntimeError('JSONBIN_MASTER_KEY oder JSONBIN_BIN_ID nicht gesetzt')
    resp = requests.get(
        f'{BASE_URL}/{JSONBIN_BIN}/latest',
        headers={'X-Master-Key': JSONBIN_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get('record', {})


def write_bin(document):
    """Overwrite the JSONBin document. Raises RuntimeError if credentials
    are missing, or requests.HTTPError on a non-2xx response."""
    if not JSONBIN_KEY or not JSONBIN_BIN:
        raise RuntimeError('JSONBIN_MASTER_KEY oder JSONBIN_BIN_ID nicht gesetzt')
    resp = requests.put(
        f'{BASE_URL}/{JSONBIN_BIN}',
        json=document,
        headers={'X-Master-Key': JSONBIN_KEY, 'Content-Type': 'application/json'},
        timeout=15,
    )
    resp.raise_for_status()
    return True
