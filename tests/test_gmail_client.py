import base64
from unittest.mock import MagicMock, patch

import pytest

from agent import gmail_client
from agent.gmail_client import GmailMessage, WrongAccountError


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _mock_service_for(execute_return_value):
    """Build a MagicMock shaped like service.users().messages().get(...).execute()
    (and .list()/.trash()) all returning `execute_return_value`.
    """
    service = MagicMock()
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = (
        execute_return_value
    )
    return service


# ---- header/body parsing -----------------------------------------------------

FULL_PAYLOAD = {
    "id": "msg1",
    "threadId": "thread1",
    "payload": {
        "mimeType": "multipart/alternative",
        "headers": [
            {"name": "From", "value": "ACME Deals <Sales@ACME-Mail.example.com>"},
            {"name": "Subject", "value": "50% off everything!"},
            {"name": "Date", "value": "Mon, 1 Jan 2026 00:00:00 +0000"},
            {"name": "List-Unsubscribe", "value": "<mailto:unsub@acme.example.com>"},
        ],
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("Plain text body")}},
            {"mimeType": "text/html", "body": {"data": _b64("<html>HTML body</html>")}},
        ],
    },
}

METADATA_PAYLOAD = {
    "id": "msg1",
    "threadId": "thread1",
    "payload": {
        "headers": [
            {"name": "From", "value": "ACME Deals <Sales@ACME-Mail.example.com>"},
            {"name": "Subject", "value": "50% off everything!"},
            {"name": "Date", "value": "Mon, 1 Jan 2026 00:00:00 +0000"},
        ],
    },
}


def test_get_message_full_parses_headers_and_bodies():
    service = _mock_service_for(FULL_PAYLOAD)

    msg = gmail_client.get_message_full(service, "msg1")

    assert msg == GmailMessage(
        message_id="msg1",
        thread_id="thread1",
        sender_email="sales@acme-mail.example.com",  # lowercased
        subject="50% off everything!",
        date="Mon, 1 Jan 2026 00:00:00 +0000",
        headers={
            "From": "ACME Deals <Sales@ACME-Mail.example.com>",
            "Subject": "50% off everything!",
            "Date": "Mon, 1 Jan 2026 00:00:00 +0000",
            "List-Unsubscribe": "<mailto:unsub@acme.example.com>",
        },
        body_text="Plain text body",
        body_html="<html>HTML body</html>",
    )


def test_get_message_metadata_leaves_body_none():
    service = _mock_service_for(METADATA_PAYLOAD)

    msg = gmail_client.get_message_metadata(service, "msg1")

    assert msg.sender_email == "sales@acme-mail.example.com"
    assert msg.subject == "50% off everything!"
    assert msg.body_text is None
    assert msg.body_html is None


def test_get_message_metadata_requests_only_metadata_headers():
    service = _mock_service_for(METADATA_PAYLOAD)

    gmail_client.get_message_metadata(service, "msg1")

    _, kwargs = service.users().messages().get.call_args
    assert kwargs["format"] == "metadata"
    assert set(kwargs["metadataHeaders"]) == {"From", "Subject", "Date", "List-Unsubscribe"}


def test_extract_bodies_skips_attachment_parts():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "application/pdf", "body": {"attachmentId": "abc"}},
            {"mimeType": "text/plain", "body": {"data": _b64("real body")}},
        ],
    }

    body_text, body_html = gmail_client._extract_bodies(payload)

    assert body_text == "real body"
    assert body_html is None


# ---- search pagination --------------------------------------------------------

def test_search_messages_paginates_until_no_next_token():
    service = MagicMock()
    list_execute = service.users.return_value.messages.return_value.list.return_value.execute
    list_execute.side_effect = [
        {"messages": [{"id": "a"}, {"id": "b"}], "nextPageToken": "page2"},
        {"messages": [{"id": "c"}]},
    ]

    ids = gmail_client.search_messages(service, "category:promotions")

    assert ids == ["a", "b", "c"]
    assert list_execute.call_count == 2


def test_search_messages_handles_zero_results():
    service = MagicMock()
    list_execute = service.users.return_value.messages.return_value.list.return_value.execute
    list_execute.return_value = {}

    ids = gmail_client.search_messages(service, "category:promotions subject:zzz")

    assert ids == []


# ---- trash ---------------------------------------------------------------------

def test_trash_message_calls_trash_not_delete():
    service = MagicMock()

    gmail_client.trash_message(service, "msg1")

    service.users.return_value.messages.return_value.trash.assert_called_once_with(
        userId="me", id="msg1"
    )
    service.users.return_value.messages.return_value.trash.return_value.execute.assert_called_once()
    assert not service.users.return_value.messages.return_value.delete.called


# ---- account verification -------------------------------------------------------

def test_verify_account_passes_on_case_insensitive_match():
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "Bob.Taylor.MBA@Gmail.com"
    }

    gmail_client.verify_account(service, "bob.taylor.mba@gmail.com")  # must not raise


def test_verify_account_raises_on_mismatch():
    service = MagicMock()
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "someone.else@gmail.com"
    }

    with pytest.raises(WrongAccountError):
        gmail_client.verify_account(service, "bob.taylor.mba@gmail.com")


# ---- credentials branching (mocked, no real network/OAuth) ----------------------

class _FakeCreds:
    def __init__(self, valid=True, expired=False, refresh_token="rt"):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refreshed = False

    def refresh(self, request):
        self.refreshed = True
        self.valid = True

    def to_json(self):
        return "{}"


def test_get_credentials_reuses_cached_valid_token(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    fake_creds = _FakeCreds(valid=True)

    with patch.object(gmail_client.Credentials, "from_authorized_user_file", return_value=fake_creds), \
         patch.object(gmail_client, "InstalledAppFlow") as mock_flow:
        creds = gmail_client.get_credentials(tmp_path / "client_secret.json", token_path, ["scope"])

    assert creds is fake_creds
    mock_flow.from_client_secrets_file.assert_not_called()


def test_get_credentials_refreshes_expired_token(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text("{}")
    fake_creds = _FakeCreds(valid=False, expired=True, refresh_token="rt")

    with patch.object(gmail_client.Credentials, "from_authorized_user_file", return_value=fake_creds), \
         patch.object(gmail_client, "InstalledAppFlow") as mock_flow:
        creds = gmail_client.get_credentials(tmp_path / "client_secret.json", token_path, ["scope"])

    assert fake_creds.refreshed is True
    mock_flow.from_client_secrets_file.assert_not_called()
    assert token_path.read_text() == "{}"  # re-persisted after refresh


def test_get_credentials_runs_interactive_flow_when_no_token(tmp_path):
    token_path = tmp_path / "token.json"
    client_secret_path = tmp_path / "client_secret.json"
    fake_creds = _FakeCreds(valid=True)
    mock_flow_instance = MagicMock()
    mock_flow_instance.run_local_server.return_value = fake_creds

    with patch.object(gmail_client, "InstalledAppFlow") as mock_flow_cls:
        mock_flow_cls.from_client_secrets_file.return_value = mock_flow_instance
        creds = gmail_client.get_credentials(client_secret_path, token_path, ["scope"])

    mock_flow_cls.from_client_secrets_file.assert_called_once_with(str(client_secret_path), ["scope"])
    assert creds is fake_creds
    assert token_path.exists()
