from unittest.mock import patch, MagicMock
from scripts.send_email import send_digest_email, build_email_message


def test_build_email_message_has_correct_subject():
    msg = build_email_message(
        subject="[DailyPaper] 2026-03-03 每日论文精选",
        html_body="<html><body>Test</body></html>",
        sender="bot@gmail.com",
        recipients=["user@example.com"],
    )
    assert msg["Subject"] == "[DailyPaper] 2026-03-03 每日论文精选"
    assert msg["From"] == "bot@gmail.com"
    assert msg["To"] == "user@example.com"


def test_send_digest_email_calls_smtp(mocker):
    mock_smtp = mocker.patch("smtplib.SMTP_SSL")
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    send_digest_email(
        date="2026-03-03",
        html_body="<html>Test</html>",
        gmail_user="bot@gmail.com",
        gmail_password="secret",
        recipients=["user@example.com"],
        subject_prefix="[DailyPaper]",
    )

    mock_smtp.assert_called_once_with("smtp.gmail.com", 465)
    mock_server.login.assert_called_once_with("bot@gmail.com", "secret")
    mock_server.send_message.assert_called_once()
