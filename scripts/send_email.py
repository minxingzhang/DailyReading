import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List


def build_email_message(
    subject: str, html_body: str, sender: str, recipients: List[str]
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_digest_email(
    date: str,
    html_body: str,
    gmail_user: str,
    gmail_password: str,
    recipients: List[str],
    subject_prefix: str = "[DailyPaper]",
) -> None:
    subject = f"{subject_prefix} {date} 每日论文精选"
    msg = build_email_message(subject, html_body, gmail_user, recipients)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
