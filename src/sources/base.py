import os
from abc import ABC, abstractmethod


class Source(ABC):
    """一個備份來源。opts 來自 [job:<name>] 區段。"""

    extension = '.bin'   # 備份檔副檔名（含壓縮）

    def __init__(self, name: str, opts: dict[str, str]):
        self.name = name
        self.opts = opts

    def secret(self, key: str = 'password_env') -> str:
        """從 opts 指定的環境變數名稱讀取機密，例如 password_env = MYSQL_BACKUP_PASSWORD。"""
        env_name = self.opts.get(key, '')
        return os.environ.get(env_name, '') if env_name else ''

    def require(self, *keys: str) -> None:
        missing = [k for k in keys if not self.opts.get(k)]
        if missing:
            raise ValueError(f'[job:{self.name}] 缺少設定：{", ".join(missing)}')

    @abstractmethod
    def dump(self, out_path: str) -> None:
        """產生備份檔到 out_path（已壓縮）。"""

    @abstractmethod
    def restore(self, backup_path: str, target: str | None = None) -> None:
        """從備份檔還原。"""
