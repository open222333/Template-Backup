import smtplib
from email.message import EmailMessage

from src import get_bool, get_int, get_setting
from src.notify.base import Notifier


class MailNotifier(Notifier):
    """SMTP 寄信。密碼請用環境變數 SMTP_PASSWORD。"""

    name = 'mail'

    def __init__(self):
        self.host = get_setting('MAIL', 'SMTP_HOST')
        self.port = get_int('MAIL', 'SMTP_PORT', 587)
        self.user = get_setting('MAIL', 'SMTP_USER')
        self.password = get_setting('MAIL', 'SMTP_PASSWORD')
        self.use_ssl = get_bool('MAIL', 'SMTP_SSL', False)
        self.sender = get_setting('MAIL', 'MAIL_FROM', self.user)
        self.to = [a.strip() for a in get_setting('MAIL', 'MAIL_TO').split(',') if a.strip()]

    def enabled(self) -> bool:
        return bool(self.host and self.sender and self.to)

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.sender
        msg['To'] = ', '.join(self.to)
        msg.set_content(body)
        if self.use_ssl:
            server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=15)
        with server:
            if not self.use_ssl:
                server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.send_message(msg)
