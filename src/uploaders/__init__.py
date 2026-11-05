from src.uploaders.base import NoopUploader, Uploader


def build_uploader(kind: str | None = None) -> Uploader:
    from src import get_setting
    kind = kind or get_setting('UPLOAD', 'UPLOADER', 'none')
    if kind == 'none':
        return NoopUploader()
    if kind == 'rclone':
        from src.uploaders.rclone import RcloneUploader
        return RcloneUploader()
    if kind == 's3':
        from src.uploaders.s3 import S3Uploader
        return S3Uploader()
    raise ValueError(f'未知的 UPLOADER：{kind}（可用 none / rclone / s3）')


__all__ = ['Uploader', 'build_uploader']
