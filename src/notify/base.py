import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Notifier(ABC):
    name = 'base'

    def enabled(self) -> bool:
        return True

    @abstractmethod
    def send(self, subject: str, body: str) -> None:
        ...


class ConsoleNotifier(Notifier):
    name = 'console'

    def send(self, subject: str, body: str) -> None:
        logger.info('[通知] %s\n%s', subject, body)
