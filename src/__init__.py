from configparser import ConfigParser
from os import environ
from os.path import abspath, dirname, join


# 專案根目錄（不受執行時工作目錄影響）
BASE_DIR = dirname(dirname(abspath(__file__)))

config = ConfigParser()
config.read(join(BASE_DIR, 'conf', 'config.ini'), encoding='utf-8')


def get_setting(section: str, key: str, fallback: str = '') -> str:
    """讀取設定值，優先順序：環境變數 > conf/config.ini > fallback。

    範例：
        LOG_LEVEL = get_setting('LOG', 'LOG_LEVEL', 'INFO')
    """
    value = environ.get(key)
    if value:
        return value
    return config.get(section, key, fallback=fallback)


def get_int(section: str, key: str, fallback: int) -> int:
    return int(get_setting(section, key, str(fallback)))


def get_float(section: str, key: str, fallback: float) -> float:
    return float(get_setting(section, key, str(fallback)))


def get_bool(section: str, key: str, fallback: bool = False) -> bool:
    return get_setting(section, key, str(fallback)).strip().lower() in ('1', 'true', 'yes', 'on')


LOG_LEVEL = get_setting('LOG', 'LOG_LEVEL', 'INFO')
