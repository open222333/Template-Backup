import os
import subprocess

from src.sources.base import Source
from src.util import run_pipeline


class MongoSource(Source):
    """mongodump --archive --gzip。

    opts: uri_env（存放連線字串的環境變數名稱，例如 MONGO_BACKUP_URI）、db（選填）、extra_args
    連線字串含帳密，只放環境變數。
    """

    extension = '.archive.gz'

    def _uri(self) -> str:
        uri = self.secret('uri_env')
        if not uri:
            raise ValueError(f'[job:{self.name}] 環境變數 {self.opts.get("uri_env")} 未設定連線字串')
        return uri

    def dump_cmd(self) -> list[str]:
        cmd = ['mongodump', '--archive', '--gzip']
        if self.opts.get('db'):
            cmd += ['--db', self.opts['db']]
        return cmd + self.opts.get('extra_args', '').split()

    def dump(self, out_path: str) -> None:
        # --uri 以 config 檔傳入，避免出現在 process 參數
        cfg = out_path + '.mongo.yaml'
        with open(cfg, 'w', encoding='utf-8') as f:
            f.write(f'uri: "{self._uri()}"\n')
        os.chmod(cfg, 0o600)
        try:
            run_pipeline([*self.dump_cmd(), f'--config={cfg}'], out_path)
        finally:
            os.remove(cfg)

    def restore(self, backup_path: str, target: str | None = None) -> None:
        cfg = backup_path + '.mongo.yaml'
        with open(cfg, 'w', encoding='utf-8') as f:
            f.write(f'uri: "{self._uri()}"\n')
        os.chmod(cfg, 0o600)
        try:
            cmd = ['mongorestore', '--archive=' + backup_path, '--gzip', '--drop', f'--config={cfg}']
            if target:
                src_db = self.opts.get('db') or target
                cmd += [f'--nsFrom={src_db}.*', f'--nsTo={target}.*']
            r = subprocess.run(cmd)
            if r.returncode:
                raise RuntimeError(f'mongorestore 失敗（{r.returncode}）')
        finally:
            os.remove(cfg)
