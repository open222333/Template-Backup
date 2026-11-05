"""統一 logging 設定：輸出到 console 與 logs/app.log。"""
import logging
import os
from logging.handlers import RotatingFileHandler

from src import BASE_DIR, LOG_LEVEL

_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_logging(level: str = LOG_LEVEL, log_file: str = 'app.log') -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(console)

    log_dir = os.path.join(BASE_DIR, 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(os.path.join(log_dir, log_file), maxBytes=5 * 1024 * 1024,
                                 backupCount=3, encoding='utf-8')
        fh.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(fh)
    except OSError:
        root.warning('無法寫入 logs/，僅輸出到 console')
