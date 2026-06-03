"""Download Track A competition files via the Kaggle API.

Reads the API token from $KAGGLE_API_TOKEN (preferred) or a `kaggle.json`
at $KAGGLE_CONFIG_DIR / ~/.kaggle/kaggle.json.

Usage:
  export KAGGLE_API_TOKEN=KGAT_xxxxxxxxxxxxxxxxxxxxxxxx
  python scripts/download_data.py
"""
from __future__ import annotations
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

COMP = 'ml-gen-x-bioreasoning-challenge-track-a'
FILES = ['train.csv', 'test.csv']

def get_token() -> str | None:
    if t := os.environ.get('KAGGLE_API_TOKEN'):
        return t
    cfg = Path(os.environ.get('KAGGLE_CONFIG_DIR', Path.home() / '.kaggle')) / 'kaggle.json'
    if cfg.exists():
        d = json.loads(cfg.read_text())
        return d.get('key') or d.get('api_token') or d.get('token')
    return None

def download(token: str, fname: str, out: Path):
    url = f'https://www.kaggle.com/api/v1/competitions/data/download/{COMP}/{fname}'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    print(f'  fetching {fname} ...', end=' ', flush=True)
    try:
        with urllib.request.urlopen(req) as r:
            data = r.read()
        out.write_bytes(data)
        print(f'ok ({len(data)} bytes)')
    except urllib.error.HTTPError as e:
        print(f'FAILED ({e.code} {e.reason})')
        sys.exit(1)

def main():
    token = get_token()
    if not token:
        print('ERROR: set KAGGLE_API_TOKEN env var or place kaggle.json under ~/.kaggle/.')
        sys.exit(1)
    for f in FILES:
        out = DATA / f
        if out.exists():
            print(f'  {f}: exists ({out.stat().st_size} bytes), skipping')
            continue
        download(token, f, out)
    print('done.')

if __name__ == '__main__':
    main()
