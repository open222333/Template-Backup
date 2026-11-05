"""備份流程：dump（已壓縮）→ checksum → 本機輪替 → 上傳 → 遠端輪替 → 通知。"""
import logging
import os
import time
from dataclasses import dataclass, field

from src import BASE_DIR, config, get_int, get_setting
from src.notify import Notifier, send_all
from src.rotation import select_expired
from src.sources import REGISTRY, Source
from src.uploaders import Uploader
from src.util import human_size, timestamp, write_checksum

logger = logging.getLogger(__name__)


def backup_root() -> str:
    p = get_setting('BACKUP', 'BACKUP_DIR', 'data/backups')
    return p if os.path.isabs(p) else os.path.join(BASE_DIR, p)


@dataclass
class Job:
    name: str
    source: Source
    keep_local: int
    keep_remote: int

    @property
    def dir(self) -> str:
        return os.path.join(backup_root(), self.name)

    def local_files(self) -> list[str]:
        if not os.path.isdir(self.dir):
            return []
        return sorted(f for f in os.listdir(self.dir) if not f.endswith('.sha256'))


@dataclass
class JobResult:
    job: str
    ok: bool
    path: str = ''
    size: int = 0
    seconds: float = 0.0
    remote: str = ''
    error: str = ''
    removed: list[str] = field(default_factory=list)


def load_jobs(cfg=config, names: list[str] | None = None) -> list[Job]:
    default_local = get_int('BACKUP', 'KEEP_LOCAL', 7)
    default_remote = get_int('BACKUP', 'KEEP_REMOTE', 30)
    jobs = []
    for section in cfg.sections():
        if not section.startswith('job:'):
            continue
        name = section.split(':', 1)[1]
        opts = dict(cfg.items(section))
        if names and name not in names:
            continue
        if not names and opts.get('enabled', 'true').lower() in ('0', 'false', 'no', 'off'):
            continue
        cls = REGISTRY.get(opts.get('type', ''))
        if cls is None:
            raise ValueError(f'[{section}] 未知的 type：{opts.get("type")}（可用：{", ".join(REGISTRY)}）')
        jobs.append(Job(name, cls(name, opts),
                        int(opts.get('keep_local', default_local)),
                        int(opts.get('keep_remote', default_remote))))
    if names:
        missing = set(names) - {j.name for j in jobs}
        if missing:
            raise ValueError(f'找不到 job：{", ".join(sorted(missing))}')
    return jobs


def rotate_local(job: Job) -> list[str]:
    removed = []
    for f in select_expired(job.local_files(), job.keep_local):
        for p in (os.path.join(job.dir, f), os.path.join(job.dir, f + '.sha256')):
            if os.path.exists(p):
                os.remove(p)
        removed.append(f)
    return removed


def rotate_remote(job: Job, uploader: Uploader) -> list[str]:
    files = uploader.list(job.name)
    removed = []
    for f in select_expired(files, job.keep_remote):
        uploader.delete(job.name, f)
        if f + '.sha256' in files:
            uploader.delete(job.name, f + '.sha256')
        removed.append(f)
    return removed


def run_job(job: Job, uploader: Uploader) -> JobResult:
    start = time.monotonic()
    os.makedirs(job.dir, exist_ok=True)
    path = os.path.join(job.dir, f'{job.name}_{timestamp()}{job.source.extension}')
    try:
        logger.info('[%s] 開始備份 → %s', job.name, path)
        job.source.dump(path)
        checksum = write_checksum(path)
        removed = rotate_local(job)
        remote = ''
        if uploader.name != 'none':
            remote = uploader.upload(path, job.name)
            uploader.upload(checksum, job.name)
            removed += [f'remote:{f}' for f in rotate_remote(job, uploader)]
        result = JobResult(job.name, True, path, os.path.getsize(path), time.monotonic() - start, remote,
                           removed=removed)
        logger.info('[%s] 完成：%s，%.1f 秒', job.name, human_size(result.size), result.seconds)
        return result
    except Exception as e:  # noqa: BLE001 - 單一 job 失敗不影響其他 job
        logger.exception('[%s] 備份失敗', job.name)
        return JobResult(job.name, False, seconds=time.monotonic() - start, error=f'{type(e).__name__}: {e}')


def summarize(results: list[JobResult]) -> tuple[str, str]:
    host = get_setting('BACKUP', 'BACKUP_NAME', 'backup')
    failed = [r for r in results if not r.ok]
    icon = '🔴' if failed else '✅'
    subject = f'{icon} [{host}] 備份{"失敗" if failed else "完成"}：{len(results) - len(failed)}/{len(results)}'
    lines = []
    for r in results:
        if r.ok:
            line = f'✅ {r.job}：{human_size(r.size)}，{r.seconds:.1f}s'
            if r.remote:
                line += f'\n   → {r.remote}'
            if r.removed:
                line += f'\n   輪替刪除 {len(r.removed)} 份'
        else:
            line = f'🔴 {r.job}：{r.error}'
        lines.append(line)
    return subject, '\n'.join(lines)


def run_all(jobs: list[Job], uploader: Uploader, notifiers: list[Notifier]) -> list[JobResult]:
    results = [run_job(j, uploader) for j in jobs]
    notify_on = get_setting('NOTIFY', 'NOTIFY_ON', 'always')    # always / failure / never
    failed = any(not r.ok for r in results)
    if notify_on == 'always' or (notify_on == 'failure' and failed):
        send_all(notifiers, *summarize(results))
    return results
