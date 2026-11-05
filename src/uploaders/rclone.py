"""rclone：支援 S3、GCS、B2、Google Drive、SFTP、WebDAV… 等數十種後端。

先用 `rclone config` 建立 remote（設定檔掛載到容器 /config/rclone/rclone.conf）。
RCLONE_REMOTE 例如 `b2:my-bucket/backups`。
"""
import os
import subprocess

from src import get_setting
from src.uploaders.base import Uploader


class RcloneUploader(Uploader):
    name = 'rclone'

    def __init__(self, remote: str | None = None, runner=subprocess.run):
        self.remote = (remote or get_setting('UPLOAD', 'RCLONE_REMOTE')).rstrip('/')
        if not self.remote:
            raise ValueError('UPLOADER=rclone 需要設定 RCLONE_REMOTE')
        self.extra = get_setting('UPLOAD', 'RCLONE_EXTRA_ARGS', '').split()
        self._run = runner

    def _rclone(self, *args: str) -> str:
        r = self._run(['rclone', *args, *self.extra], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f'rclone {args[0]} 失敗：{r.stderr.strip()}')
        return r.stdout

    def upload(self, local_path, job):
        dest = f'{self.remote}/{job}'
        self._rclone('copy', local_path, dest)
        return f'{dest}/{os.path.basename(local_path)}'

    def list(self, job):
        try:
            out = self._rclone('lsf', '--files-only', f'{self.remote}/{job}')
        except RuntimeError:
            return []   # 目錄尚不存在
        return [ln.strip() for ln in out.splitlines() if ln.strip()]

    def delete(self, job, filename):
        self._rclone('deletefile', f'{self.remote}/{job}/{filename}')
