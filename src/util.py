import hashlib
import os
import re
import subprocess
from datetime import datetime, timezone

TS_FORMAT = '%Y%m%d-%H%M%S'
_TS_RE = re.compile(r'_(\d{8}-\d{6})\.')


def timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime(TS_FORMAT)


def parse_timestamp(filename: str) -> datetime | None:
    m = _TS_RE.search(filename)
    return datetime.strptime(m.group(1), TS_FORMAT).replace(tzinfo=timezone.utc) if m else None


def sha256sum(path: str, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def write_checksum(path: str) -> str:
    digest = sha256sum(path)
    with open(path + '.sha256', 'w', encoding='utf-8') as f:
        f.write(f'{digest}  {os.path.basename(path)}\n')
    return path + '.sha256'


def verify_checksum(path: str) -> bool:
    try:
        with open(path + '.sha256', encoding='utf-8') as f:
            expected = f.read().split()[0]
    except (OSError, IndexError):
        return False
    return sha256sum(path) == expected


def human_size(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} PB'


def run_pipeline(cmd: list[str], out_path: str, env: dict[str, str] | None = None,
                 gzip_output: bool = False) -> None:
    """執行指令並把 stdout 寫入檔案（可選 gzip）。失敗時刪除不完整檔案並拋出例外。

    密碼一律經 env 傳入，不放在 cmd（避免出現在 ps / log）。
    """
    full_env = {**os.environ, **(env or {})}
    try:
        with open(out_path, 'wb') as out:
            if gzip_output:
                p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=full_env)
                p2 = subprocess.Popen(['gzip', '-c'], stdin=p1.stdout, stdout=out, stderr=subprocess.PIPE)
                p1.stdout.close()
                _, err2 = p2.communicate()
                err1 = p1.stderr.read()
                p1.wait()
                if p1.returncode != 0:
                    raise RuntimeError(f'{cmd[0]} 失敗（{p1.returncode}）：{err1.decode(errors="replace").strip()}')
                if p2.returncode != 0:
                    raise RuntimeError(f'gzip 失敗：{err2.decode(errors="replace").strip()}')
            else:
                r = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, env=full_env)
                if r.returncode != 0:
                    raise RuntimeError(f'{cmd[0]} 失敗（{r.returncode}）：{r.stderr.decode(errors="replace").strip()}')
    except BaseException:
        if os.path.exists(out_path):
            os.remove(out_path)
        raise
