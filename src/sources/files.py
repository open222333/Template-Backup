import fnmatch
import os
import tarfile

from src.sources.base import Source


class FilesSource(Source):
    """檔案 / 目錄打包成 tar.gz。

    opts: paths（逗號分隔）、exclude（逗號分隔 glob，例如 *.log,node_modules）
    """

    extension = '.tar.gz'

    def _excluded(self, name: str) -> bool:
        patterns = [p.strip() for p in self.opts.get('exclude', '').split(',') if p.strip()]
        base = os.path.basename(name)
        return any(fnmatch.fnmatch(base, p) or fnmatch.fnmatch(name, p) for p in patterns)

    def dump(self, out_path: str) -> None:
        self.require('paths')
        paths = [p.strip() for p in self.opts['paths'].split(',') if p.strip()]
        for p in paths:
            if not os.path.exists(p):
                raise FileNotFoundError(f'[job:{self.name}] 路徑不存在：{p}')
        try:
            with tarfile.open(out_path, 'w:gz') as tar:
                for p in paths:
                    tar.add(p, arcname=os.path.basename(os.path.normpath(p)),
                            filter=lambda ti: None if self._excluded(ti.name) else ti)
        except BaseException:
            if os.path.exists(out_path):
                os.remove(out_path)
            raise

    def restore(self, backup_path: str, target: str | None = None) -> None:
        if not target:
            raise ValueError('files 還原需要指定 --target 目錄（不會覆寫原路徑）')
        os.makedirs(target, exist_ok=True)
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(target, filter='data')   # 防止路徑穿越
