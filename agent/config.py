"""Shared constants and filesystem paths for the agent: the age threshold
and search query from SPEC.md Section 6.1, and the data-store/credentials
paths from Section 5 and 8.3. No logic lives here — just values other
modules read.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Section 5 — data store
STORE_PATH = REPO_ROOT / "data" / "store.json"
SEED_PATH = REPO_ROOT / "data" / "store.seed.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "store.schema.json"

# credentials/ is gitignored (never committed) — see .gitignore and
# docs/SPEC.md Section 8.3.
CREDENTIALS_DIR = REPO_ROOT / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

# Section 6.1 — first-pass filter (Appendix B)
DEFAULT_AGE_THRESHOLD_DAYS = 14
GMAIL_SEARCH_QUERY_TEMPLATE = "category:promotions older_than:{days}d"

# gmail.modify covers trash/untrash and label changes without requesting
# the broader https://mail.google.com/ scope, which also allows permanent
# delete. Requesting the narrower scope backs up the Trash-only guardrail
# in Section 8.2 at the permissions level, not just in application logic.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
