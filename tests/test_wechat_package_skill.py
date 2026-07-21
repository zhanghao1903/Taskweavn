"""Installed ``wechat-use`` package skill integration tests."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from wechat_desktop_tool import load_wechat_use_skill

from taskweavn.context import ContextBuildRequest
from taskweavn.core import WorkspaceLayout
from taskweavn.integrations.wechat_tool.skill import (
    WECHAT_USE_SKILL_ID,
    wechat_use_skill_descriptor,
)
from taskweavn.server.main_page_agent import build_agent_loop_resident_default_agent
from taskweavn.task import InMemoryTaskBus, TaskDomain
from taskweavn.wechat_task_types import WECHAT_SEND_CAPABILITY


def test_installed_wechat_skill_is_adapted_without_copying_resources() -> None:
    packaged = load_wechat_use_skill()
    descriptor = wechat_use_skill_descriptor()

    assert version("wechat-desktop-tool") == "0.3.0"
    assert packaged.version == "1.0.0"
    assert descriptor.skill_id == WECHAT_USE_SKILL_ID
    assert descriptor.instruction_body == packaged.instructions
    assert descriptor.source_ref == (
        "pypi://wechat-desktop-tool/0.3.0/skills/wechat-use@1.0.0"
    )
    assert descriptor.content_hash.startswith("sha256:")
    assert descriptor.tool_policy.requested_tools == ("wechat_desktop",)
    assert descriptor.tool_policy.denied_tools == ("computer_use",)
    assert descriptor.context_requirements == (
        "execution_agent",
        WECHAT_SEND_CAPABILITY,
    )
    assert {resource.path.rsplit("/", 1)[-1] for resource in descriptor.resource_refs} == {
        "operations.md",
        "recovery.md",
    }


def test_wechat_skill_adapter_supports_cold_process_import() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from taskweavn.integrations.wechat_tool.skill import "
                "wechat_use_skill_descriptor; "
                "assert wechat_use_skill_descriptor().skill_id == 'managed:wechat-use'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_wechat_execution_task_receives_packaged_skill_context(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path / "workspace")
    layout.bootstrap()
    task = TaskDomain(
        task_id="task-wechat",
        session_id="session-wechat",
        root_id="task-wechat",
        intent="给微信的文件传输助手发送你好",
        required_capability=WECHAT_SEND_CAPABILITY,
        created_by="test",
    )
    task_bus = InMemoryTaskBus((task,))
    agent = build_agent_loop_resident_default_agent(
        layout=layout,
        llm=object(),
        task_bus=task_bus,
        enable_computer_use_tool=True,
    )

    assert agent.context_builder_factory is not None
    result = agent.context_builder_factory(task).build(
        ContextBuildRequest(
            session_id=task.session_id,
            task_id=task.task_id,
            agent_run_id="run-wechat",
            render_mode="start_context",
        )
    )

    assert result.trace.active_skill_ids == (WECHAT_USE_SKILL_ID,)
    assert result.context.controls.denied_tools == ("computer_use",)
    assert "wechat-use" in result.rendered.user_content
    assert "Prefer one authorized `send_message` call" in result.rendered.user_content
    assert "focus_contact and draft_message" not in result.rendered.user_content


def test_wechat_package_skill_is_not_loaded_when_computer_use_is_disabled(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout(tmp_path / "workspace")
    layout.bootstrap()
    task = TaskDomain(
        task_id="task-wechat-disabled",
        session_id="session-wechat-disabled",
        root_id="task-wechat-disabled",
        intent="给微信的文件传输助手发送你好",
        required_capability=WECHAT_SEND_CAPABILITY,
        created_by="test",
    )
    task_bus = InMemoryTaskBus((task,))
    agent = build_agent_loop_resident_default_agent(
        layout=layout,
        llm=object(),
        task_bus=task_bus,
        enable_computer_use_tool=False,
    )

    assert agent.context_builder_factory is not None
    result = agent.context_builder_factory(task).build(
        ContextBuildRequest(
            session_id=task.session_id,
            task_id=task.task_id,
            agent_run_id="run-wechat-disabled",
            render_mode="start_context",
        )
    )

    assert result.trace.active_skill_ids == ()
    assert "wechat-use" not in result.rendered.user_content
