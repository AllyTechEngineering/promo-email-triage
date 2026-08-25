import json
from pathlib import Path

import pytest

from agent import store

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "data" / "store.seed.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "store.schema.json"


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "store.json"


def test_first_run_seeds_store_from_seed_file(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)

    assert store_path.exists()
    assert "doris1122@icloud.com" in data["sender_decisions"]
    assert data["sender_decisions"]["doris1122@icloud.com"]["decision"] == "whitelist"
    assert data["trashed_log"] == []


def test_subsequent_run_does_not_reseed(store_path):
    store.load_store(store_path, SEED_PATH, SCHEMA_PATH)
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)
    store.set_sender_decision(
        data, "new@example.com", "blacklist", "user_confirmed", store_path
    )

    reloaded = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)
    assert "new@example.com" in reloaded["sender_decisions"]


def test_save_store_is_atomic_replace(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)
    original_inode_dir_contents = list(store_path.parent.iterdir())

    store.save_store(data, store_path)

    # No leftover temp files after a successful write.
    assert list(store_path.parent.iterdir()) == original_inode_dir_contents
    with open(store_path) as f:
        json.load(f)  # must still be valid JSON


def test_save_store_leaves_no_temp_file_on_write_failure(store_path, monkeypatch):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)

    def boom(*args, **kwargs):
        raise OSError("simulated crash mid-write")

    monkeypatch.setattr(json, "dump", boom)

    with pytest.raises(OSError):
        store.save_store(data, store_path)

    # Original file must be untouched, and no .tmp file left behind.
    with open(store_path) as f:
        json.load(f)
    leftover_tmp_files = list(store_path.parent.glob("*.tmp"))
    assert leftover_tmp_files == []


def test_load_store_rejects_invalid_json(store_path):
    store_path.write_text("{not valid json")

    with pytest.raises(store.StoreValidationError):
        store.load_store(store_path, SEED_PATH, SCHEMA_PATH)


def test_load_store_rejects_schema_violation(store_path):
    store_path.write_text(json.dumps({"meta": {}, "sender_decisions": {}}))  # missing trashed_log

    with pytest.raises(store.StoreValidationError):
        store.load_store(store_path, SEED_PATH, SCHEMA_PATH)


def test_load_store_rejects_malformed_timestamp(store_path):
    # Otherwise schema-valid, but meta.updated_at isn't a real date-time.
    # jsonschema.validate() silently ignores "format" keywords unless a
    # FormatChecker is passed, and even then "date-time" isn't registered
    # without rfc3339-validator installed — this test exists specifically
    # to prove that gap is actually closed, not just documented.
    store_path.write_text(
        json.dumps(
            {
                "meta": {"schema_version": "1.1.0", "updated_at": "not-a-real-timestamp"},
                "sender_decisions": {},
                "trashed_log": [],
            }
        )
    )

    with pytest.raises(store.StoreValidationError):
        store.load_store(store_path, SEED_PATH, SCHEMA_PATH)


def test_get_sender_decision_is_case_insensitive(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)

    decision = store.get_sender_decision(data, "DORIS1122@ICLOUD.COM")
    assert decision is not None
    assert decision["decision"] == "whitelist"


def test_get_sender_decision_unknown_sender_returns_none(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)
    assert store.get_sender_decision(data, "nobody@example.com") is None


def test_set_sender_decision_persists_immediately(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)

    store.set_sender_decision(
        data, "AMBIGUOUS@Example.com", "blacklist", "user_confirmed", store_path,
        notes="resolved via ask-once",
    )

    on_disk = json.loads(store_path.read_text())
    assert "ambiguous@example.com" in on_disk["sender_decisions"]
    assert on_disk["sender_decisions"]["ambiguous@example.com"]["decision"] == "blacklist"
    assert on_disk["sender_decisions"]["ambiguous@example.com"]["source"] == "user_confirmed"


def test_set_sender_decision_preserves_created_at_on_update(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)
    store.set_sender_decision(data, "a@example.com", "pending", "agent_inferred", store_path)
    first_created_at = data["sender_decisions"]["a@example.com"]["created_at"]

    store.set_sender_decision(data, "a@example.com", "blacklist", "user_confirmed", store_path)

    assert data["sender_decisions"]["a@example.com"]["created_at"] == first_created_at
    assert data["sender_decisions"]["a@example.com"]["decision"] == "blacklist"


def test_is_already_trashed(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)
    store.append_trashed_log_entry(
        data, "msg-1", "thread-1", "spammer@example.com", "Big Sale!!"
    )

    assert store.is_already_trashed(data, "msg-1") is True
    assert store.is_already_trashed(data, "msg-2") is False


def test_append_trashed_log_entry_does_not_persist_until_explicit_save(store_path):
    data = store.load_store(store_path, SEED_PATH, SCHEMA_PATH)

    store.append_trashed_log_entry(
        data, "msg-1", "thread-1", "spammer@example.com", "Big Sale!!"
    )

    on_disk = json.loads(store_path.read_text())
    assert on_disk["trashed_log"] == []  # not yet saved

    store.save_store(data, store_path)

    on_disk = json.loads(store_path.read_text())
    assert len(on_disk["trashed_log"]) == 1
    assert on_disk["trashed_log"][0]["message_id"] == "msg-1"
