"""Golden JSON fixtures shared by backend and frontend contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from taskweavn.server.ui_contract import (
    CommandResponse,
    MainPageSnapshot,
    QueryResponse,
    UiEvent,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ui_contract"


def test_main_page_snapshot_fixture_is_canonical_contract_json() -> None:
    payload = _load_json("main_page_snapshot.min.json")

    response = QueryResponse[MainPageSnapshot].model_validate(payload)

    assert response.model_dump(mode="json") == payload


def test_command_response_fixture_is_canonical_contract_json() -> None:
    payload = _load_json("command_response.accepted.json")

    response = CommandResponse.model_validate(payload)

    assert response.model_dump(mode="json") == payload


def test_ui_event_fixture_is_canonical_contract_json() -> None:
    payload = _load_json("ui_event.message_appended.json")

    event = UiEvent.model_validate(payload)

    assert event.model_dump(mode="json") == payload


def _load_json(name: str) -> dict[str, object]:
    payload = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return cast(dict[str, object], payload)
