"""程式進入點。

python -m src backup [job ...]          執行備份（未指定 = 全部 enabled 的 job）
python -m src list [job ...]            列出本機與遠端備份
python -m src verify <備份檔>           檢查 checksum 與壓縮檔完整性
python -m src restore <job> <備份檔> [--target X] --yes
"""
import argparse
import gzip
import logging
import os
import sys
import tarfile

from src.backup import load_jobs, run_all
from src.log import setup_logging
from src.notify import build_notifiers
from src.uploaders import build_uploader
from src.util import human_size, verify_checksum

logger = logging.getLogger(__name__)


def cmd_backup(args) -> int:
    jobs = load_jobs(names=args.jobs or None)
    if not jobs:
        logger.error('沒有任何 job，請在 conf/config.ini 新增 [job:<name>] 區段')
        return 2
    results = run_all(jobs, build_uploader(), build_notifiers())
    return 0 if all(r.ok for r in results) else 1


def cmd_list(args) -> int:
    uploader = build_uploader()
    for job in load_jobs(names=args.jobs or None):
        print(f'== {job.name}（本機保留 {job.keep_local}、遠端保留 {job.keep_remote}）')
        for f in job.local_files():
            print(f'  local   {f}  {human_size(os.path.getsize(os.path.join(job.dir, f)))}')
        for f in uploader.list(job.name):
            if not f.endswith('.sha256'):
                print(f'  remote  {f}')
    return 0


def verify_file(path: str) -> tuple[bool, str]:
    if not os.path.exists(path):
        return False, '檔案不存在'
    if not verify_checksum(path):
        return False, 'checksum 不符或缺少 .sha256'
    try:
        if path.endswith('.tar.gz'):
            with tarfile.open(path, 'r:gz') as tar:
                for _ in tar:
                    pass
        elif path.endswith('.gz'):
            with gzip.open(path, 'rb') as f:
                while f.read(1024 * 1024):
                    pass
    except (OSError, EOFError, tarfile.TarError) as e:
        return False, f'壓縮檔損毀：{e}'
    return True, 'OK'


def cmd_verify(args) -> int:
    ok, msg = verify_file(args.file)
    print(f'{args.file}: {msg}')
    return 0 if ok else 1


def cmd_restore(args) -> int:
    job = load_jobs(names=[args.job])[0]
    ok, msg = verify_file(args.file)
    if not ok and not args.skip_verify:
        logger.error('備份檔驗證失敗（%s），如確定要還原請加 --skip-verify', msg)
        return 1
    if not args.yes:
        print(f'即將以 {args.file} 還原 job「{job.name}」（type={job.source.opts.get("type")}，'
              f'target={args.target or "原設定"}）。\n此操作可能覆寫既有資料，確認後加上 --yes 重新執行。')
        return 1
    job.source.restore(args.file, args.target)
    logger.info('還原完成：%s', args.file)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m src')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('backup', help='執行備份')
    p.add_argument('jobs', nargs='*')
    p.set_defaults(func=cmd_backup)
    p = sub.add_parser('list', help='列出備份')
    p.add_argument('jobs', nargs='*')
    p.set_defaults(func=cmd_list)
    p = sub.add_parser('verify', help='驗證備份檔')
    p.add_argument('file')
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser('restore', help='還原備份')
    p.add_argument('job')
    p.add_argument('file')
    p.add_argument('--target', help='files：解壓目錄；mysql / postgres / mongo：目標資料庫')
    p.add_argument('--yes', action='store_true', help='確認執行')
    p.add_argument('--skip-verify', action='store_true')
    p.set_defaults(func=cmd_restore)

    args = parser.parse_args(argv)
    setup_logging()
    try:
        return args.func(args)
    except ValueError as e:
        logger.error('%s', e)
        return 2


if __name__ == '__main__':
    sys.exit(main())
