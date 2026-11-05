"""通知模組：console / Telegram / Mail。

用法：
    from src.notify import build_notifiers, send_all
    notifiers = build_notifiers()            # 依 [NOTIFY] CHANNELS 建立
    send_all(notifiers, '標題', '內容')
"""
import logging

from src import get_setting
from src.notify.base import Notifier, ConsoleNotifier
from src.notify.mail import MailNotifier
from src.notify.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

_REGISTRY = {
    'console': ConsoleNotifier,
    'telegram': TelegramNotifier,
    'mail': MailNotifier,
}


def build_notifiers(channels: str | None = None) -> list[Notifier]:
    channels = channels if channels is not None else get_setting('NOTIFY', 'NOTIFY_CHANNELS', 'console')
    notifiers: list[Notifier] = []
    for name in [c.strip() for c in channels.split(',') if c.strip()]:
        cls = _REGISTRY.get(name)
        if cls is None:
            logger.warning('未知的通知管道：%s', name)
            continue
        notifier = cls()
        if notifier.enabled():
            notifiers.append(notifier)
        else:
            logger.warning('通知管道 %s 設定不完整，已略過', name)
    return notifiers


def send_all(notifiers: list[Notifier], subject: str, body: str) -> bool:
    """送出到所有管道；任一成功即回傳 True。單一管道失敗不影響其他管道。"""
    ok = False
    for n in notifiers:
        try:
            n.send(subject, body)
            ok = True
        except Exception:  # noqa: BLE001 - 通知失敗不可中斷主流程
            logger.exception('通知失敗：%s', n.name)
    return ok


__all__ = ['Notifier', 'build_notifiers', 'send_all']
