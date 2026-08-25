"""MANUAL SMOKE TEST — not part of the automated suite in tests/.

Requires: a real credentials/client_secret.json (downloaded from Google
Cloud Console), live network access, and an interactive browser for the
first-run OAuth consent screen.

Proves: OAuth consent completes, the resulting token is persisted, and
get_authenticated_service() genuinely refuses to proceed unless the
authenticated account matches config.EXPECTED_GMAIL_ACCOUNT.

Procedure:
  1. Run: python scripts/smoke_test_auth.py
     A browser window should open for Google sign-in + consent. Approve
     it. The script should then print the success line below.
  2. Confirm credentials/token.json now exists.
  3. Run this script AGAIN immediately. The browser must NOT reopen —
     it should print the same success line instantly. That's what proves
     the cached/refreshed token path works, not just first-run consent.
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

# If we reach this line, verify_account() already confirmed the
# authenticated account matches config.EXPECTED_GMAIL_ACCOUNT — a
# WrongAccountError would have stopped execution above otherwise.
print("Authenticated and verified as:", config.EXPECTED_GMAIL_ACCOUNT)
