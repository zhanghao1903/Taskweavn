from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from taskweavn.types import ComputerUseObservation


def test_helper_preflight_reports_missing_accessibility_and_skips_wechat(
    tmp_path: Path,
) -> None:
    module = _load_script()
    _patch_backend(
        module,
        ComputerUseObservation(
            operation="readiness",
            status="not_available",
            success=False,
            summary="missing accessibility",
            metadata={
                "readiness": {
                    "status": "missing_accessibility",
                    "accessibility_trusted": False,
                },
                "failure_kind": "missing_accessibility",
                "helper_status": "missing_accessibility",
                "setup_hint": "Grant Accessibility to helper.",
                "recovery_actions": ["open_macos_privacy_accessibility"],
            },
        ),
    )
    manifest = tmp_path / "computer-use-helper.json"
    manifest.write_text(
        json.dumps(
            {
                "endpoint": "http://127.0.0.1:49152",
                "token": "secret-token",
                "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
            }
        ),
        encoding="utf-8",
    )

    result = module.run_helper_preflight(
        module.HelperPreflightConfig(
            helper_manifest=manifest,
            helper_app_path=tmp_path / "Helper.app",
            check_wechat_app=True,
        )
    )

    assert result.ready is False
    assert result.helper_ready is False
    assert result.package_readiness_status == "missing_accessibility"
    assert result.wechat_app_phase == "helper_package_readiness"
    assert result.wechat_app_failure_kind == "missing_accessibility"
    assert result.helper_manifest == {
        "endpoint": "http://127.0.0.1:49152",
        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
    }


def test_helper_preflight_checks_wechat_app_when_helper_ready(
    tmp_path: Path,
) -> None:
    module = _load_script()
    _patch_backend(
        module,
        ComputerUseObservation(
            operation="readiness",
            status="ok",
            success=True,
            summary="helper ready",
            metadata={
                "readiness": {
                    "status": "ready",
                    "accessibility_trusted": True,
                },
                "helper_status": "ready",
                "diagnostics": {
                    "runtimeIdentity": {"mode": "helper_owned_executable"}
                },
            },
        ),
    )
    seen_configs: list[Any] = []

    def fake_wechat_readiness(config: object) -> dict[str, Any]:
        seen_configs.append(config)
        return {
            "status": "ok",
            "success": True,
            "summary": "WeChat window ready.",
            "phase": "window_readiness",
            "diagnostics": {"windowCount": 1},
        }

    module._helper_wechat_app_readiness = fake_wechat_readiness

    result = module.run_helper_preflight(
        module.HelperPreflightConfig(
            helper_manifest=tmp_path / "missing-ok-for-test.json",
            helper_app_path=tmp_path / "Helper.app",
            check_wechat_app=True,
        )
    )

    assert result.ready is True
    assert result.helper_ready is True
    assert result.wechat_app_success is True
    assert result.wechat_app_phase == "window_readiness"
    assert result.runtime_identity == {"mode": "helper_owned_executable"}
    assert len(seen_configs) == 1


def test_helper_preflight_writes_evidence(tmp_path: Path) -> None:
    module = _load_script()
    _patch_backend(
        module,
        ComputerUseObservation(
            operation="readiness",
            status="ok",
            success=True,
            summary="helper ready",
            metadata={"readiness": {"status": "ready"}},
        ),
    )
    evidence = tmp_path / "preflight.json"

    exit_code = module._run(
        module.HelperPreflightConfig(
            helper_manifest=tmp_path / "computer-use-helper.json",
            helper_app_path=tmp_path / "Helper.app",
            evidence_output=evidence,
        )
    )

    assert exit_code == 0
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["kind"] == "computer_use_helper_preflight"
    assert payload["checkWeChatApp"] is False
    assert payload["result"]["ready"] is True


def _patch_backend(
    module: ModuleType,
    observation: ComputerUseObservation,
) -> None:
    class FakeBackend:
        def __init__(self, *, config: object) -> None:
            self.config = config

        def readiness(self) -> ComputerUseObservation:
            return observation

    module.ComputerUseHelperBackend = FakeBackend


def _load_script() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "manual_computer_use_helper_preflight.py"
    )
    spec = importlib.util.spec_from_file_location(
        "manual_computer_use_helper_preflight",
        script_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(ModuleType, module)
