"""Tests for UI command response idempotency stores."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from taskweavn.server import (
    HttpApiResponse,
    InMemoryUiCommandResponseIdempotencyStore,
    SqliteUiCommandResponseIdempotencyStore,
    UiCommandResponseIdempotencyRecord,
    UiCommandResponseIdempotencyStore,
)


def _record() -> UiCommandResponseIdempotencyRecord:
    return UiCommandResponseIdempotencyRecord.from_response(
        session_id="s1",
        idempotency_key="generate-1",
        request_hash="hash-1",
        response=HttpApiResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body={
                "requestId": "command-1",
                "ok": True,
                "result": {"status": "accepted"},
            },
        ),
    )


def test_in_memory_ui_command_idempotency_store_protocol_conformance() -> None:
    store = InMemoryUiCommandResponseIdempotencyStore()

    assert isinstance(store, UiCommandResponseIdempotencyStore)


def test_sqlite_ui_command_idempotency_store_reopens(tmp_path: Path) -> None:
    db = tmp_path / "ui_commands.sqlite"
    first = SqliteUiCommandResponseIdempotencyStore(db)
    record = _record()
    try:
        saved = first.put(record)
        replay = first.put(replace(record, request_hash="hash-2"))

        assert saved == record
        assert replay == record
    finally:
        first.close()

    second = SqliteUiCommandResponseIdempotencyStore(db)
    try:
        loaded = second.get("s1", "generate-1")

        assert loaded == record
        assert loaded is not None
        assert loaded.to_response().body == record.body
    finally:
        second.close()
