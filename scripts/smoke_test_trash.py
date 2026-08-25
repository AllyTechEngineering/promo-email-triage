"""MANUAL SMOKE TEST — not part of the automated suite in tests/.

Prerequisite: run scripts/smoke_test_auth.py successfully first.

SAFETY PREREQUISITE — do this manually before running this script:
Send yourself one throwaway email, from bob.taylor.mba@gmail.com to
itself, with subject exactly:

    [GMAIL-CLIENT SMOKE TEST] <current ISO timestamp>

The timestamp makes it impossible to confuse with a previous run's
leftover test message. This script refuses to proceed unless it finds
EXACTLY ONE message matching that subject fragment — it will never
select a message from a broader or ambiguous search, because the whole
safety property of this test depends on targeting one message you
personally just created, not one discovered by real scan logic.

After running, verify in the Gmail web UI (don't just trust the API
response below):
  1. The message is visible in Trash.
  2. Restore it from Trash back to Inbox and confirm it reappears intact.
     This is what actually proves trash_message() only calls Gmail's
     trash endpoint and never a permanent delete (SPEC.md Section 8.2) —
     if it had called delete() instead, this recovery step would fail.
  3. Afterward, leave it in Inbox or re-trash it and let Gmail's Trash
     auto-purge it in 30 days. Never permanent-delete it manually either.
"""

import sys
from pathlib import Path

# Running this file directly (rather than `python -m`) puts scripts/ itself
# on sys.path, not the repo root — so agent/, a sibling directory, isn't
# importable unless we add the repo root ourselves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import config, gmail_client  # noqa: E402

service = gmail_client.get_authenticated_service(
    client_secret_path=config.CLIENT_SECRET_PATH,
    token_path=config.TOKEN_PATH,
    scopes=config.GMAIL_SCOPES,
    expected_email=config.EXPECTED_GMAIL_ACCOUNT,
)

ids = gmail_client.search_messages(service, 'subject:"[GMAIL-CLIENT SMOKE TEST]"')
assert len(ids) == 1, (
    f"expected exactly 1 match, got {len(ids)} — STOP, do not trash anything "
    "until this is resolved (clean up stale test messages first)"
)
target_id = ids[0]

msg = gmail_client.get_message_metadata(service, target_id)
print("About to trash:", msg.sender_email, "|", msg.subject)
input("Press Enter to confirm and trash this exact message, or Ctrl+C to abort: ")

gmail_client.trash_message(service, target_id)

result = service.users().messages().get(userId="me", id=target_id).execute()
assert "TRASH" in result["labelIds"]
assert "INBOX" not in result["labelIds"]
print("Confirmed via API: message is in Trash, not Inbox.")
print("Now manually check Gmail's Trash folder, then restore it to Inbox to confirm recoverability.")
