from abc import ABC, abstractmethod


class Uploader(ABC):
    name = 'base'

    @abstractmethod
    def upload(self, local_path: str, job: str) -> str:
        """上傳檔案到 <remote>/<job>/，回傳遠端位置。"""

    @abstractmethod
    def list(self, job: str) -> list[str]:
        """列出 <remote>/<job>/ 下的檔名。"""

    @abstractmethod
    def delete(self, job: str, filename: str) -> None:
        ...


class NoopUploader(Uploader):
    """不上傳（只保留本機）。"""

    name = 'none'

    def upload(self, local_path, job):
        return ''

    def list(self, job):
        return []

    def delete(self, job, filename):
        pass
