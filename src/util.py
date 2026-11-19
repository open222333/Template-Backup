import hashlib
import os
import re
import subprocess
import tempfile
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


def _read_err(f) -> str:
    f.seek(0)
    return f.read()[-4000:].decode(errors='replace').strip()   # 只保留結尾，避免訊息過長


def run_pipeline(cmd: list[str], out_path: str, env: dict[str, str] | None = None,
                 gzip_output: bool = False) -> None:
    """執行指令並把 stdout 寫入檔案（可選 gzip）。失敗時刪除不完整檔案並拋出例外。

    密碼一律經 env 傳入，不放在 cmd（避免出現在 ps / log）。
    stderr 寫入暫存檔而不是 PIPE：指令輸出大量錯誤訊息時，PIPE 緩衝區滿了會讓程序互相等待而卡死。
    """
    full_env = {**os.environ, **(env or {})}
    try:
        with open(out_path, 'wb') as out, tempfile.TemporaryFile() as err1, tempfile.TemporaryFile() as err2:
            if gzip_output:
                p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err1, env=full_env)
                p2 = subprocess.Popen(['gzip', '-c'], stdin=p1.stdout, stdout=out, stderr=err2)
                p1.stdout.close()   # 讓 gzip 結束時 p1 能收到 SIGPIPE
                p2.wait()
                p1.wait()
                if p1.returncode != 0:
                    raise RuntimeError(f'{cmd[0]} 失敗（{p1.returncode}）：{_read_err(err1)}')
                if p2.returncode != 0:
                    raise RuntimeError(f'gzip 失敗：{_read_err(err2)}')
            else:
                r = subprocess.run(cmd, stdout=out, stderr=err1, env=full_env)
                if r.returncode != 0:
                    raise RuntimeError(f'{cmd[0]} 失敗（{r.returncode}）：{_read_err(err1)}')
    except BaseException:
        if os.path.exists(out_path):
            os.remove(out_path)
        raise
