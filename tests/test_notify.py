from unittest import mock

from src.notify import build_notifiers, send_all
from src.notify.base import Notifier
from src.notify.telegram import TelegramNotifier


class _Boom(Notifier):
    name = 'boom'

    def send(self, subject, body):
        raise RuntimeError('fail')


class _Ok(Notifier):
    name = 'ok'

    def __init__(self):
        self.sent = []

    def send(self, subject, body):
        self.sent.append((subject, body))


def test_send_all_continues_after_failure():
    ok = _Ok()
    assert send_all([_Boom(), ok], 's', 'b') is True
    assert ok.sent == [('s', 'b')]


def test_incomplete_channel_skipped(monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
    names = [n.name for n in build_notifiers('console,telegram,unknown')]
    assert names == ['console']


def test_telegram_posts_message():
    n = TelegramNotifier(token='T', chat_id='42')
    with mock.patch('src.notify.telegram.requests.post') as post:
        n.send('subj', 'body')
    url = post.call_args.args[0]
    assert url.endswith('/botT/sendMessage')
    assert post.call_args.kwargs['json']['chat_id'] == '42'
