"""備份來源註冊表。新增來源：繼承 Source、實作 dump() / restore_cmd()，加入 REGISTRY。"""
from src.sources.base import Source
from src.sources.files import FilesSource
from src.sources.mongo import MongoSource
from src.sources.mysql import MySQLSource
from src.sources.postgres import PostgresSource

REGISTRY: dict[str, type[Source]] = {
    'files': FilesSource,
    'mysql': MySQLSource,
    'postgres': PostgresSource,
    'mongo': MongoSource,
}

__all__ = ['Source', 'REGISTRY']
