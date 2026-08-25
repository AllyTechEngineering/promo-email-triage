"""The only module that talks to the Gmail API directly. Everything else
(workflow.py, classify.py) deals in plain GmailMessage values, never in
googleapiclient/OAuth objects. See docs/SPEC.md Section 6.1 (search),
Section 7 (workflow), and Section 8.2 (Trash-only safety guardrail).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class WrongAccountError(Exception):
    """Raised when the authenticated Gmail account doesn't match the
    expected account. Guards against a stale or mis-consented token.json
    silently running search/trash against the wrong mailbox — a real risk
    since the OAuth consent screen's account picker is easy to mis-click
    when multiple Google accounts are signed in.
    """


@dataclass(frozen=True)
class GmailMessage:
    message_id: str
    thread_id: str
    sender_email: str  # lowercased — must match store.py's lowercase key
    # convention or whitelist/blacklist lookups silently miss.
    subject: str
    date: str
    headers: dict[str, str]  # raw, so classify.py can inspect List-Unsubscribe,
    # Received, Return-Path etc. without this module knowing what a "signal" is.
    body_text: str | None  # None for metadata-only fetches
    body_html: str | None


def _parse_sender_email(from_header: str) -> str:
    _, address = parseaddr(from_header)
    return address.lower()


def _headers_dict(payload: dict[str, Any]) -> dict[str, str]:
    return {h["name"]: h["value"] for h in payload.get("headers", [])}


def _decode_base64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_bodies(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Recursively walk a full-format message payload for the first
    text/plain and text/html parts. Skips attachment parts (no inline
    body.data). Only meaningful for format="full" — metadata-only
    responses have no nested body content to walk.
    """
    body_text: str | None = None
    body_html: str | None = None
    stack = [payload]
    while stack:
        part = stack.pop()
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime_type == "text/plain" and body_text is None:
            body_text = _decode_base64url(data)
        elif data and mime_type == "text/html" and body_html is None:
            body_html = _decode_base64url(data)
        stack.extend(part.get("parts") or [])
    return body_text, body_html


def get_credentials(client_secret_path: Path, token_path: Path, scopes: list[str]) -> Credentials:
    """Load cached credentials from token_path, refreshing if expired, or
    run the one-time interactive browser consent flow if no usable token
    exists. Persists the resulting/refreshed credentials back to
    token_path — a plain write, not the atomic-replace pattern required
    for data/store.json (Section 5.5): that requirement is scoped to the
    data store specifically, and a rare corrupted token write just forces
    re-consent, not data loss.
    """
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return creds


def build_service(credentials: Credentials):
    return build("gmail", "v1", credentials=credentials)


def verify_account(service, expected_email: str) -> None:
    profile = service.users().getProfile(userId="me").execute()
    actual_email = profile["emailAddress"]
    if actual_email.lower() != expected_email.lower():
        raise WrongAccountError(
            f"Authenticated as {actual_email!r}, expected {expected_email!r}. "
            "Refusing to proceed — delete credentials/token.json and "
            "re-authenticate as the correct account."
        )


def get_authenticated_service(
    client_secret_path: Path, token_path: Path, scopes: list[str], expected_email: str
):
    """The one sanctioned way to get a working Gmail service: auth, build,
    and verify the account in one call, so the WrongAccountError guardrail
    can't be silently skipped by a caller that forgets to wire it in.
    """
    credentials = get_credentials(client_secret_path, token_path, scopes)
    service = build_service(credentials)
    verify_account(service, expected_email)
    return service


def search_messages(service, query: str) -> list[str]:
    """Return every message ID matching `query`, paginating through
    Gmail's nextPageToken until exhausted.
    """
    message_ids: list[str] = []
    page_token: str | None = None
    while True:
        request_kwargs: dict[str, Any] = {"userId": "me", "q": query}
        if page_token:
            request_kwargs["pageToken"] = page_token
        response = service.users().messages().list(**request_kwargs).execute()
        message_ids.extend(m["id"] for m in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return message_ids


def get_message_metadata(service, message_id: str) -> GmailMessage:
    """Cheap fetch: headers only, no body. Enough to identify the sender
    for the whitelist/blacklist pre-filter (Section 7 steps 2-3) and to
    check the List-Unsubscribe header — one of Section 6.2's four signals
    — without paying for a full MIME body fetch.
    """
    result = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe"],
        )
        .execute()
    )
    headers = _headers_dict(result["payload"])
    return GmailMessage(
        message_id=result["id"],
        thread_id=result["threadId"],
        sender_email=_parse_sender_email(headers.get("From", "")),
        subject=headers.get("Subject", ""),
        date=headers.get("Date", ""),
        headers=headers,
        body_text=None,
        body_html=None,
    )


def get_message_full(service, message_id: str) -> GmailMessage:
    """Full fetch including decoded body text/html, needed for the
    remaining Section 6.2 signals (tracking pixel, mail-merge artifacts,
    ESP sending infrastructure). Only worth calling for candidates whose
    sender isn't already resolved whitelist/blacklist.
    """
    result = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = _headers_dict(result["payload"])
    body_text, body_html = _extract_bodies(result["payload"])
    return GmailMessage(
        message_id=result["id"],
        thread_id=result["threadId"],
        sender_email=_parse_sender_email(headers.get("From", "")),
        subject=headers.get("Subject", ""),
        date=headers.get("Date", ""),
        headers=headers,
        body_text=body_text,
        body_html=body_html,
    )


def trash_message(service, message_id: str) -> None:
    """Move a message to Trash. There is deliberately no wrapper for
    messages().delete() anywhere in this file — the Trash-only guardrail
    in SPEC.md Section 8.2 is enforced structurally: this module simply
    has no function capable of a permanent delete.
    """
    service.users().messages().trash(userId="me", id=message_id).execute()
