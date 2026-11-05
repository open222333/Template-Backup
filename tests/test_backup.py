import configparser
import os
import tarfile
from datetime import datetime, timezone

import pytest

from src import backup as bk
from src.__main__ import main, verify_file
from src.notify.base import Notifier
from src.rotation import select_expired
from src.sources.files import FilesSource
from src.sources.mongo import MongoSource
from src.sources.mysql import MySQLSource
from src.sources.postgres import PostgresSource
from src.uploaders.base import Uploader
from src.uploaders.rclone import RcloneUploader
from src.util import parse_timestamp, timestamp, verify_checksum, write_checksum


def test_timestamp_roundtrip():
    now = datetime(2026, 11, 5, 3, 17, 0, tzinfo=timezone.utc)
    assert parse_timestamp(f'db_{timestamp(now)}.sql.gz') == now
    assert parse_timestamp('random.txt') is None


def test_select_expired_keeps_newest():
    files = [f'j_2026110{d}-000000.sql.gz' for d in range(1, 6)] + ['j_20261105-000000.sql.gz.sha256', 'notes.txt']
    assert select_expired(files, 2) == ['j_20261103-000000.sql.gz', 'j_20261102-000000.sql.gz',
                                        'j_20261101-000000.sql.gz']
    assert select_expired(files, 0) == []


def test_files_source_dump_and_restore(tmp_path):
    src_dir = tmp_path / 'site'
    (src_dir / 'sub').mkdir(parents=True)
    (src_dir / 'a.txt').write_text('hello')
    (src_dir / 'debug.log').write_text('skip')
    (src_dir / 'sub' / 'b.txt').write_text('world')
    out = tmp_path / 'b.tar.gz'
    FilesSource('f', {'paths': str(src_dir), 'exclude': '*.log'}).dump(str(out))
    names = tarfile.open(out).getnames()
    assert 'site/a.txt' in names and 'site/sub/b.txt' in names and 'site/debug.log' not in names
    FilesSource('f', {}).restore(str(out), str(tmp_path / 'restore'))
    assert (tmp_path / 'restore' / 'site' / 'a.txt').read_text() == 'hello'
    with pytest.raises(ValueError):
        FilesSource('f', {}).restore(str(out), None)


def test_files_source_missing_path(tmp_path):
    out = tmp_path / 'x.tar.gz'
    with pytest.raises(FileNotFoundError):
        FilesSource('f', {'paths': str(tmp_path / 'nope')}).dump(str(out))
    assert not out.exists()


def test_db_commands_have_no_password():
    my = MySQLSource('m', {'host': 'h', 'user': 'u', 'password_env': 'X', 'databases': 'a, b'})
    cmd = my.dump_cmd()
    assert cmd[:7] == ['mysqldump', '-h', 'h', '-P', '3306', '-u', 'u']
    assert cmd[-3:] == ['--databases', 'a', 'b'] and '--single-transaction' in cmd
    assert MySQLSource('m', {'host': 'h', 'user': 'u'}).dump_cmd()[-1] == '--all-databases'
    pg = PostgresSource('p', {'host': 'h', 'user': 'u', 'database': 'app'}).dump_cmd()
    assert pg[0] == 'pg_dump' and '-Fc' in pg and pg[-1] == 'app'
    assert MongoSource('g', {'db': 'x'}).dump_cmd() == ['mongodump', '--archive', '--gzip', '--db', 'x']
    with pytest.raises(ValueError):
        PostgresSource('p', {'host': 'h'}).dump_cmd()


def test_secret_from_env(monkeypatch):
    monkeypatch.setenv('MY_PW', 's3cret')
    assert MySQLSource('m', {'password_env': 'MY_PW'}).secret() == 's3cret'


def test_checksum_and_verify(tmp_path):
    f = tmp_path / 'j_20261105-000000.tar.gz'
    with tarfile.open(f, 'w:gz') as tar:
        tar.add(__file__, arcname='t.py')
    assert not verify_checksum(str(f))
    write_checksum(str(f))
    assert verify_file(str(f)) == (True, 'OK')
    f.write_bytes(b'corrupt')
    assert verify_file(str(f))[0] is False


class MemUploader(Uploader):
    name = 'mem'

    def __init__(self):
        self.store: dict[str, list[str]] = {}

    def upload(self, local_path, job):
        self.store.setdefault(job, []).append(os.path.basename(local_path))
        return f'mem://{job}/{os.path.basename(local_path)}'

    def list(self, job):
        return list(self.store.get(job, []))

    def delete(self, job, filename):
        self.store[job].remove(filename)


class Collect(Notifier):
    name = 'collect'

    def __init__(self):
        self.msgs = []

    def send(self, subject, body):
        self.msgs.append((subject, body))


def _cfg(tmp_path, body):
    cfg = configparser.ConfigParser()
    cfg.read_string(body)
    return cfg


def test_run_all_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv('BACKUP_DIR', str(tmp_path / 'backups'))
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'x.txt').write_text('x')
    cfg = _cfg(tmp_path, f"""
[job:files]
type=files
paths={data}
keep_local=2
keep_remote=1
[job:broken]
type=files
paths={tmp_path / 'missing'}
[job:off]
type=files
paths={data}
enabled=false
""")
    jobs = bk.load_jobs(cfg)
    assert [j.name for j in jobs] == ['files', 'broken']
    up, n = MemUploader(), Collect()
    stamps = iter(s for d in ('20261101', '20261102', '20261103') for s in (f'{d}-000000', f'{d}-000001'))
    monkeypatch.setattr(bk, 'timestamp', lambda: next(stamps))
    for _ in range(3):
        results = bk.run_all(jobs, up, [n])
    assert [r.ok for r in results] == [True, False]
    assert sorted(os.listdir(tmp_path / 'backups' / 'files')) == [
        'files_20261102-000000.tar.gz', 'files_20261102-000000.tar.gz.sha256',
        'files_20261103-000000.tar.gz', 'files_20261103-000000.tar.gz.sha256']
    assert sorted(up.store['files']) == ['files_20261103-000000.tar.gz', 'files_20261103-000000.tar.gz.sha256']
    subject, body = n.msgs[-1]
    assert '失敗' in subject and '1/2' in subject and 'FileNotFoundError' in body


def test_load_jobs_unknown_name(tmp_path):
    cfg = _cfg(tmp_path, '[job:a]\ntype=files\npaths=/\n')
    with pytest.raises(ValueError):
        bk.load_jobs(cfg, names=['zzz'])


def test_rclone_uploader_commands():
    calls = []

    class R:
        returncode, stdout, stderr = 0, 'a_20261101-000000.sql.gz\nb.txt\n', ''

    def runner(cmd, **kw):
        calls.append(cmd)
        return R()

    up = RcloneUploader('b2:bucket/backups/', runner=runner)
    assert up.upload('/tmp/a_20261101-000000.sql.gz', 'db') == 'b2:bucket/backups/db/a_20261101-000000.sql.gz'
    assert up.list('db') == ['a_20261101-000000.sql.gz', 'b.txt']
    up.delete('db', 'b.txt')
    assert calls[0][:3] == ['rclone', 'copy', '/tmp/a_20261101-000000.sql.gz']
    assert calls[2][:3] == ['rclone', 'deletefile', 'b2:bucket/backups/db/b.txt']


def test_restore_requires_yes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('BACKUP_DIR', str(tmp_path))
    f = tmp_path / 'f.tar.gz'
    FilesSource('f', {'paths': __file__}).dump(str(f))
    write_checksum(str(f))
    monkeypatch.setattr(bk, 'config', _cfg(tmp_path, f'[job:f]\ntype=files\npaths={__file__}\n'))
    monkeypatch.setattr('src.__main__.load_jobs', lambda names=None: bk.load_jobs(bk.config, names))
    assert main(['restore', 'f', str(f), '--target', str(tmp_path / 'out')]) == 1
    assert not (tmp_path / 'out').exists()
    assert main(['restore', 'f', str(f), '--target', str(tmp_path / 'out'), '--yes']) == 0
    assert (tmp_path / 'out').exists()


def test_run_pipeline_gzip_and_failure(tmp_path):
    import gzip as gz
    from src.util import run_pipeline
    out = tmp_path / 'o.gz'
    run_pipeline(['echo', 'dump-data'], str(out), gzip_output=True)
    assert gz.open(out).read() == b'dump-data\n'
    bad = tmp_path / 'bad.gz'
    with pytest.raises(RuntimeError):
        run_pipeline(['sh', '-c', 'echo partial; echo boom >&2; exit 3'], str(bad), gzip_output=True)
    assert not bad.exists()
