"""Owns data/store.json: seeding, schema validation, atomic writes, and typed
accessors. See docs/SPEC.md Section 5. No other module should read or write
data/store.json directly.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema


class StoreValidationError(Exception):
    """Raised when data/store.json fails schema validation. Callers must
    halt and alert rather than proceeding with unvalidated data (SPEC.md
    Section 8.1) or silently overwriting it.
    """


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(data: dict[str, Any], path: Path) -> None:
    """Write `data` to `path` via write-temp-then-rename, per SPEC.md
    Section 5.5. os.replace is atomic on both POSIX and Windows, so a crash
    mid-write can never leave `path` truncated or invalid.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise


def _validate(data: dict[str, Any], schema_path: Path) -> None:
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        raise StoreValidationError(f"data/store.json failed schema validation: {e.message}") from e


def load_store(store_path: Path, seed_path: Path, schema_path: Path) -> dict[str, Any]:
    """Load data/store.json, seeding it from data/store.seed.json on first
    run (SPEC.md Section 5.3). Validates against schema/store.schema.json
    before returning; raises StoreValidationError rather than trusting an
    invalid store (Section 8.1).
    """
    if not store_path.exists():
        shutil.copyfile(seed_path, store_path)

    with open(store_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise StoreValidationError(f"data/store.json is not valid JSON: {e}") from e

    _validate(data, schema_path)
    return data


def save_store(store: dict[str, Any], store_path: Path) -> None:
    """Bump meta.updated_at and atomically persist `store` to `store_path`."""
    store["meta"]["updated_at"] = _now()
    _atomic_write(store, store_path)


def get_sender_decision(store: dict[str, Any], email: str) -> dict[str, Any] | None:
    return store["sender_decisions"].get(email.lower())


def set_sender_decision(
    store: dict[str, Any],
    email: str,
    decision: str,
    source: str,
    store_path: Path,
    notes: str | None = None,
) -> None:
    """Insert or update one sender decision and persist immediately.

    Unlike append_trashed_log_entry, this writes to disk before returning
    rather than waiting for a caller to batch a save. FR-5 requires that a
    resolved ambiguous sender is never asked about again; the store is the
    only record of that resolution, so a crash between the user's answer
    and a deferred save would silently break that guarantee. A trashed
    message, by contrast, is already out of the inbox via the Gmail API
    call regardless of whether the log write lands, so trashed_log entries
    are safe to batch (see append_trashed_log_entry).
    """
    key = email.lower()
    now = _now()
    existing = store["sender_decisions"].get(key)
    store["sender_decisions"][key] = {
        "decision": decision,
        "source": source,
        "notes": notes,
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
    }
    save_store(store, store_path)


def is_already_trashed(store: dict[str, Any], message_id: str) -> bool:
    return any(entry["message_id"] == message_id for entry in store["trashed_log"])


def append_trashed_log_entry(
    store: dict[str, Any],
    message_id: str,
    thread_id: str,
    sender_email: str,
    subject: str,
    trashed_at: str | None = None,
) -> None:
    """Append one trashed-message record in memory only. The caller
    (workflow.py) is responsible for calling save_store once after a batch
    of these calls — see the persistence-timing note in set_sender_decision
    for why this one is safe to batch while sender decisions are not.
    """
    store["trashed_log"].append(
        {
            "message_id": message_id,
            "thread_id": thread_id,
            "sender_email": sender_email,
            "subject": subject,
            "trashed_at": trashed_at or _now(),
        }
    )
