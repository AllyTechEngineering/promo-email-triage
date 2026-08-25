"""MANUAL SMOKE TEST — not part of the automated suite in tests/.

Prerequisite: run scripts/smoke_test_auth.py successfully first.

Proves: category:promotions older_than:{N}d search returns real results
from the live inbox, and get_message_metadata() parses sender/subject/date
correctly for actual mail (not just synthetic fixtures).

Procedure:
  1. Run: python scripts/smoke_test_search.py
  2. Open Gmail's own Promotions tab in the browser at the same time.
  3. Manually confirm at least 2-3 of the printed sender/subject pairs are
     genuinely visible there and are actually older than the threshold —
     this checks the wrapper's output against ground truth you can see,
     not just that it didn't crash.
  4. Confirm the zero-result query prints 0 without raising.
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

query = config.GMAIL_SEARCH_QUERY_TEMPLATE.format(days=config.DEFAULT_AGE_THRESHOLD_DAYS)
ids = gmail_client.search_messages(service, query)
print(f"Query: {query}")
print(f"Matched {len(ids)} messages")
for message_id in ids[:5]:
    msg = gmail_client.get_message_metadata(service, message_id)
    print(f"- {msg.sender_email} | {msg.subject} | {msg.date}")

empty_ids = gmail_client.search_messages(
    service, "category:promotions subject:zzz_no_such_subject_zzz"
)
print(f"Zero-result query matched: {len(empty_ids)}")
