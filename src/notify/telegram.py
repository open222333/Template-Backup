import requests

from src import get_setting
from src.notify.base import Notifier


class TelegramNotifier(Notifier):
    """Telegram Bot API。Token 請用環境變數 TELEGRAM_BOT_TOKEN，勿寫入版控。"""

    name = 'telegram'
    API = 'https://api.telegram.org/bot{token}/sendMessage'

    def __init__(self, token: str | None = None, chat_id: str | None = None, timeout: int = 10):
        self.token = token or get_setting('TELEGRAM', 'TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or get_setting('TELEGRAM', 'TELEGRAM_CHAT_ID')
        self.timeout = timeout

    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, subject: str, body: str) -> None:
        text = f'{subject}\n\n{body}'[:4000]  # Telegram 單則上限 4096 字
        resp = requests.post(
            self.API.format(token=self.token),
            json={'chat_id': self.chat_id, 'text': text, 'disable_web_page_preview': True},
            timeout=self.timeout,
        )
        resp.raise_for_status()
