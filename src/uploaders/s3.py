"""S3 / S3 相容儲存（MinIO、R2、Wasabi…）。需安裝 boto3。

金鑰使用 AWS 標準環境變數：AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY。
"""
import os

from src import get_setting
from src.uploaders.base import Uploader


class S3Uploader(Uploader):
    name = 's3'

    def __init__(self, client=None):
        self.bucket = get_setting('UPLOAD', 'S3_BUCKET')
        self.prefix = get_setting('UPLOAD', 'S3_PREFIX', 'backups').strip('/')
        if not self.bucket:
            raise ValueError('UPLOADER=s3 需要設定 S3_BUCKET')
        if client is None:
            try:
                import boto3
            except ImportError as e:  # pragma: no cover
                raise RuntimeError('UPLOADER=s3 需要安裝 boto3（pip install boto3）') from e
            client = boto3.client('s3', endpoint_url=get_setting('UPLOAD', 'S3_ENDPOINT_URL') or None)
        self.client = client

    def _key(self, job: str, filename: str = '') -> str:
        return '/'.join(p for p in (self.prefix, job, filename) if p)

    def upload(self, local_path, job):
        key = self._key(job, os.path.basename(local_path))
        self.client.upload_file(local_path, self.bucket, key)
        return f's3://{self.bucket}/{key}'

    def list(self, job):
        prefix = self._key(job) + '/'
        names, token = [], None
        while True:
            kw = {'Bucket': self.bucket, 'Prefix': prefix, **({'ContinuationToken': token} if token else {})}
            resp = self.client.list_objects_v2(**kw)
            names += [o['Key'][len(prefix):] for o in resp.get('Contents', [])]
            if not resp.get('IsTruncated'):
                return names
            token = resp['NextContinuationToken']

    def delete(self, job, filename):
        self.client.delete_object(Bucket=self.bucket, Key=self._key(job, filename))
