"""Tests for the Plato adapter over the optional macOS computer-use package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskweavn.tools import MacOSComputerUseBackend
from taskweavn.types import ComputerUseAction


@dataclass(frozen=True)
class FakeReadiness:
    status: str
    setup_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "setup_hint": self.setup_hint}


@dataclass(frozen=True)
class FakeRisk:
    level: str = "high"
    requires_confirmation: bool = True
    reason: str = "external message"

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FakeResult:
    operation: str
    status: str
    success: bool
    summary: str
    text_extract: str | None = None
    snapshot_id: str | None = None
    risk: FakeRisk | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FakeMacOSClient:
    def __init__(self, *, readiness_status: str = "ready") -> None:
        self.readiness_status = readiness_status
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.next_result = FakeResult(
            operation="observe",
            status="ok",
            success=True,
            summary="Observed frontmost app.",
            text_extract="Frontmost app: TextEdit.",
            snapshot_id="frontmost:TextEdit:Untitled",
            metadata={"frontmost_app": "TextEdit"},
        )

    def readiness(self) -> FakeReadiness:
        self.calls.append(("readiness", {}))
        return FakeReadiness(self.readiness_status, "setup needed")

    def open_app(self, app: str, *, timeout: float = 10.0) -> FakeResult:
        self.calls.append(("open_app", {"app": app, "timeout": timeout}))
        return self.next_result

    def observe(
        self,
        *,
        target_app: str | None = None,
        timeout: float = 5.0,
    ) -> FakeResult:
        self.calls.append(("observe", {"target_app": target_app, "timeout": timeout}))
        return self.next_result

    def type_text(
        self,
        text: str,
        *,
        target_app: str | None = None,
        timeout: float = 5.0,
    ) -> FakeResult:
        self.calls.append(
            ("type_text", {"text": text, "target_app": target_app, "timeout": timeout})
        )
        return self.next_result

    def click(
        self,
        target: str,
        *,
        target_app: str | None = None,
        snapshot_id: str | None = None,
        timeout: float = 5.0,
        confirmed: bool = False,
        role_hints: tuple[str, ...] = ("AXButton",),
        aliases: tuple[str, ...] = (),
        max_nodes: int = 200,
        max_depth: int = 6,
        lookup_timeout: float | None = None,
        click_timeout: float | None = None,
        post_click_observe: bool = True,
    ) -> FakeResult:
        self.calls.append(
            (
                "click",
                {
                    "target": target,
                    "target_app": target_app,
                    "snapshot_id": snapshot_id,
                    "timeout": timeout,
                    "confirmed": confirmed,
                    "role_hints": role_hints,
                    "aliases": aliases,
                    "max_nodes": max_nodes,
                    "max_depth": max_depth,
                    "lookup_timeout": lookup_timeout,
                    "click_timeout": click_timeout,
                    "post_click_observe": post_click_observe,
                },
            )
        )
        return self.next_result

    def press_key(
        self,
        keys: tuple[str, ...],
        *,
        target_app: str | None = None,
        timeout: float = 5.0,
    ) -> FakeResult:
        self.calls.append(
            ("press_key", {"keys": keys, "target_app": target_app, "timeout": timeout})
        )
        return self.next_result

    def wait(self, *, seconds: float = 1.0) -> FakeResult:
        self.calls.append(("wait", {"seconds": seconds}))
        return self.next_result


def test_macos_backend_reports_package_missing_as_not_available() -> None:
    backend = MacOSComputerUseBackend(client=None)
    backend._client = None  # force deterministic package-missing behavior
    backend._import_error = "ModuleNotFoundError: test"

    observation = backend.execute(
        ComputerUseAction(operation="observe", instruction="Inspect app.")
    )

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.operation == "observe"
    assert "package is not available" in observation.summary


def test_macos_backend_maps_ready_readiness_to_ok_observation() -> None:
    client = FakeMacOSClient(readiness_status="ready")
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.execute(
        ComputerUseAction(operation="readiness", instruction="Check readiness.")
    )

    assert observation.success is True
    assert observation.status == "ok"
    assert observation.operation == "readiness"
    assert observation.metadata["readiness"]["status"] == "ready"
    diagnostics = observation.metadata["diagnostics"]
    assert diagnostics["checkedByProcessPath"]
    assert diagnostics["adapterProcessExecutable"]
    assert diagnostics["adapterArgv0"]
    assert diagnostics["packageClientClass"].endswith(".FakeMacOSClient")


def test_macos_backend_maps_missing_accessibility_to_not_available() -> None:
    client = FakeMacOSClient(readiness_status="missing_accessibility")
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.readiness()

    assert observation.success is False
    assert observation.status == "not_available"
    assert "missing_accessibility" in observation.summary
    assert observation.metadata["failure_kind"] == "missing_accessibility"


def test_macos_backend_maps_observe_result_metadata() -> None:
    client = FakeMacOSClient()
    backend = MacOSComputerUseBackend(client=client)
    action = ComputerUseAction(
        operation="observe",
        instruction="Inspect TextEdit.",
        target="TextEdit",
    )

    observation = backend.execute(action)

    assert client.calls == [("observe", {"target_app": "TextEdit", "timeout": 5.0})]
    assert observation.action_id == action.event_id
    assert observation.success is True
    assert observation.status == "ok"
    assert observation.text_extract == "Frontmost app: TextEdit."
    assert observation.metadata["snapshot_id"] == "frontmost:TextEdit:Untitled"
    assert observation.metadata["frontmost_app"] == "TextEdit"


def test_macos_backend_maps_open_type_click_and_wait_arguments() -> None:
    client = FakeMacOSClient()
    backend = MacOSComputerUseBackend(client=client)

    backend.execute(
        ComputerUseAction(
            operation="open_app",
            instruction="Open TextEdit.",
            target="TextEdit",
            timeout_seconds=7,
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="type_text",
            instruction="Type text.",
            text="hello",
            metadata={"target_app": "TextEdit"},
            timeout_seconds=3,
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="click",
            instruction="Click OK.",
            target="OK",
            metadata={"target_app": "TextEdit", "snapshot_id": "snap-1"},
            timeout_seconds=4,
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="press_key",
            instruction="Open search.",
            keys=("command", "f"),
            metadata={"target_app": "TextEdit"},
            timeout_seconds=4,
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="wait",
            instruction="Wait briefly.",
            timeout_seconds=2,
        )
    )

    assert client.calls == [
        ("open_app", {"app": "TextEdit", "timeout": 7}),
        ("type_text", {"text": "hello", "target_app": "TextEdit", "timeout": 3}),
        (
            "click",
                {
                    "target": "OK",
                    "target_app": "TextEdit",
                    "snapshot_id": "snap-1",
                    "timeout": 4,
                    "confirmed": False,
                    "role_hints": ("AXButton",),
                    "aliases": (),
                    "max_nodes": 200,
                    "max_depth": 6,
                    "lookup_timeout": None,
                    "click_timeout": None,
                    "post_click_observe": True,
                },
            ),
        (
            "press_key",
            {"keys": ("command", "f"), "target_app": "TextEdit", "timeout": 4},
        ),
        ("wait", {"seconds": 2}),
    ]


def test_macos_backend_preserves_blocked_risk_metadata() -> None:
    client = FakeMacOSClient()
    client.next_result = FakeResult(
        operation="click",
        status="blocked",
        success=False,
        summary="computer-use action requires confirmation",
        risk=FakeRisk(),
        metadata={"confirmation_required": True},
    )
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.execute(
        ComputerUseAction(
            operation="click",
            instruction="Click Send.",
            target="Send",
            metadata={"target_app": "WeChat"},
        )
    )

    assert observation.success is False
    assert observation.status == "blocked"
    assert observation.metadata["confirmation_required"] is True
    assert observation.metadata["risk"]["requires_confirmation"] is True


def test_macos_backend_passes_confirmed_click_after_product_confirmation() -> None:
    client = FakeMacOSClient()
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.execute(
        ComputerUseAction(
            operation="click",
            instruction="Click Send after product confirmation.",
            target="发送",
            metadata={"target_app": "WeChat", "confirmed_by_user": True},
        )
    )

    assert observation.status == "ok"
    assert client.calls == [
        (
            "click",
                {
                    "target": "发送",
                    "target_app": "WeChat",
                    "snapshot_id": None,
                    "timeout": 5.0,
                    "confirmed": True,
                    "role_hints": ("AXButton",),
                    "aliases": (),
                    "max_nodes": 200,
                    "max_depth": 6,
                    "lookup_timeout": None,
                    "click_timeout": None,
                    "post_click_observe": True,
                },
            )
    ]


def test_macos_backend_passes_semantic_click_options_and_preserves_w7_metadata() -> None:
    client = FakeMacOSClient()
    client.next_result = FakeResult(
        operation="click",
        status="failed",
        success=False,
        summary="Timed out while clicking semantic target.",
        metadata={
            "failure_kind": "click_timeout",
            "phase": "click",
            "lookup_attempted": True,
            "target_resolved": True,
            "click_attempted": True,
            "post_click_observed": False,
            "matched_count": 1,
        },
    )
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.execute(
        ComputerUseAction(
            operation="click",
            instruction="Click Send after product confirmation.",
            target="发送",
            metadata={
                "target_app": "WeChat",
                "confirmed_by_user": True,
                "aliases": ["发送", "Send"],
                "role_hints": ["AXButton"],
                "max_nodes": 120,
                "max_depth": 5,
                "lookup_timeout": 4.0,
                "click_timeout": 2.0,
                "post_click_observe": False,
            },
        )
    )

    assert observation.status == "failed"
    assert observation.metadata["failure_kind"] == "click_timeout"
    assert observation.metadata["phase"] == "click"
    assert observation.metadata["click_attempted"] is True
    assert observation.metadata["target_resolved"] is True
    assert client.calls == [
        (
            "click",
            {
                "target": "发送",
                "target_app": "WeChat",
                "snapshot_id": None,
                "timeout": 5.0,
                "confirmed": True,
                "role_hints": ("AXButton",),
                "aliases": ("发送", "Send"),
                "max_nodes": 120,
                "max_depth": 5,
                "lookup_timeout": 4.0,
                "click_timeout": 2.0,
                "post_click_observe": False,
            },
        )
    ]
