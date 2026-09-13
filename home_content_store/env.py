from pathlib import Path
from os import getenv, makedirs


_DATA_DIR_PATH = getenv('DATA_DIR')
if not _DATA_DIR_PATH:
    raise EnvironmentError('`DATA_DIR` is a required env var')
else:
    DATA_DIR = Path(_DATA_DIR_PATH).resolve()
    DATA_DIR.mkdir(exist_ok=True)


STREAM_DIR = DATA_DIR / "streams"
makedirs(STREAM_DIR, exist_ok=True)
