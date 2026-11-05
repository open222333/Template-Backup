import os
import subprocess

from src.sources.base import Source
from src.util import run_pipeline


class PostgresSource(Source):
    """pg_dump custom format（-Fc，本身已壓縮）。

    opts: host、port(5432)、user、password_env、database、extra_args
    pg_dump 版本需 ≥ 伺服器版本。
    """

    extension = '.dump'

    def _conn_args(self) -> list[str]:
        self.require('host', 'user', 'database')
        return ['-h', self.opts['host'], '-p', self.opts.get('port', '5432'), '-U', self.opts['user']]

    def dump_cmd(self) -> list[str]:
        return ['pg_dump', *self._conn_args(), '-Fc', '--no-password',
                *self.opts.get('extra_args', '').split(), self.opts['database']]

    def dump(self, out_path: str) -> None:
        run_pipeline(self.dump_cmd(), out_path, env={'PGPASSWORD': self.secret()})

    def restore(self, backup_path: str, target: str | None = None) -> None:
        db = target or self.opts['database']
        cmd = ['pg_restore', *self._conn_args(), '--no-password', '--clean', '--if-exists',
               '-d', db, backup_path]
        r = subprocess.run(cmd, env={**os.environ, 'PGPASSWORD': self.secret()})
        if r.returncode:
            raise RuntimeError(f'pg_restore 失敗（{r.returncode}）')
