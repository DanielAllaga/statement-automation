import os
import smtplib
from pathlib import Path
from email.message import EmailMessage


class GmailSender:
    """Reusable Gmail sender that sends plain-text emails via SMTP."""

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465

    def __init__(self, gmail_address: str | None = None, app_password: str | None = None) -> None:
        self._load_dotenv()
        self.gmail_address = gmail_address or os.getenv("GMAIL_ADDRESS")
        self.app_password = app_password or os.getenv("GMAIL_APP_PASSWORD")

        if not self.gmail_address or not self.app_password:
            raise ValueError(
                "Missing Gmail credentials. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
                "environment variables or pass them into GmailSender()."
            )

    @staticmethod
    def _load_dotenv(dotenv_path: str = ".env") -> None:
        """Load simple KEY=VALUE pairs from a local .env file into os.environ."""
        env_file = Path(dotenv_path)
        if not env_file.exists():
            return

        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
                continue

            key, value = stripped_line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

    def send_message(self, recipient: str, message: str, subject: str = "Message from GmailSender") -> None:
        email = EmailMessage()
        email["From"] = self.gmail_address
        email["To"] = recipient
        email["Subject"] = subject
        email.set_content(message)

        try:
            with smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT) as smtp:
                smtp.login(self.gmail_address, self.app_password)
                smtp.send_message(email)
        except smtplib.SMTPAuthenticationError as exc:
            raise ValueError(
                "Gmail rejected the login. Use your full Gmail address in GMAIL_ADDRESS "
                "and a Gmail App Password in GMAIL_APP_PASSWORD. Regular Gmail account "
                "passwords usually do not work for SMTP."
            ) from exc

