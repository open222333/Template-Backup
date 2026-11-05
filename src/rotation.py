"""保留最新 N 份備份。判斷依據為檔名中的時間戳（<job>_YYYYmmdd-HHMMSS.<ext>）。"""
from src.util import parse_timestamp


def select_expired(filenames: list[str], keep: int) -> list[str]:
    """回傳應刪除的備份檔（不含 .sha256，呼叫端一併刪除對應 checksum）。keep <= 0 表示不刪。"""
    if keep <= 0:
        return []
    backups = [f for f in filenames if not f.endswith('.sha256') and parse_timestamp(f)]
    backups.sort(key=parse_timestamp, reverse=True)
    return backups[keep:]
