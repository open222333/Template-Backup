import os
import subprocess

from src.sources.base import Source
from src.util import run_pipeline


class MySQLSource(Source):
    """mysqldump → gzip。

    opts: host、port(3306)、user、password_env、databases（逗號分隔；留空 = --all-databases）、extra_args
    """

    extension = '.sql.gz'

    def _conn_args(self) -> list[str]:
        self.require('host', 'user')
        return ['-h', self.opts['host'], '-P', self.opts.get('port', '3306'), '-u', self.opts['user']]

    def dump_cmd(self) -> list[str]:
        cmd = ['mysqldump', *self._conn_args(), '--single-transaction', '--quick',
               '--routines', '--events', '--triggers']
        cmd += self.opts.get('extra_args', '').split()
        dbs = [d.strip() for d in self.opts.get('databases', '').split(',') if d.strip()]
        cmd += ['--databases', *dbs] if dbs else ['--all-databases']
        return cmd

    def dump(self, out_path: str) -> None:
        run_pipeline(self.dump_cmd(), out_path, env={'MYSQL_PWD': self.secret()}, gzip_output=True)

    def restore(self, backup_path: str, target: str | None = None) -> None:
        cmd = ['mysql', *self._conn_args()] + ([target] if target else [])
        gz = subprocess.Popen(['gzip', '-dc', backup_path], stdout=subprocess.PIPE)
        r = subprocess.run(cmd, stdin=gz.stdout, env={**os.environ, 'MYSQL_PWD': self.secret()})
        gz.stdout.close()
        gz.wait()
        if r.returncode or gz.returncode:
            raise RuntimeError(f'mysql 還原失敗（mysql={r.returncode}, gzip={gz.returncode}）')
