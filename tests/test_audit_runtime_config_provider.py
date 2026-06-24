from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from taskweavn.core import Session
from taskweavn.runtime_config import (
    DefaultRuntimeConfigMutationService,
    RuntimeConfigActor,
    RuntimeConfigMutationServiceConfig,
    RuntimeConfigPatch,
    RuntimeConfigScope,
    SqliteRuntimeConfigChangeStore,
)
from taskweavn.server.runtime_config_gateway import DefaultRuntimeConfigGateway
from taskweavn.server.ui_contract.audit_detail_projection import _audit_record_detail
from taskweavn.server.ui_contract.audit_source_providers import WorkspaceAuditConfigProvider


def test_workspace_audit_config_provider_projects_runtime_config_snapshot_and_change(
    tmp_path: Path,
) -> None:
    raw_value = "model-secret-smoke-value"
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-runtime-audit",
        idempotency_key="idem-runtime-audit",
        scope=scope,
        actor=_actor(),
        values={"llm.default_model": raw_value},
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )
        change = service.apply_patch(patch)
        gateway = DefaultRuntimeConfigGateway.from_process_inputs(
            {},
            workspace_id="w1",
            change_store=store,
        )
        provider = WorkspaceAuditConfigProvider(runtime_config_gateway=gateway)
        session = _session(tmp_path)

        records = provider.list_for_session(session, task_node_id="task-1")

        assert [record.filter_kind for record in records] == ["config", "config"]
        snapshot_record = records[0]
        assert snapshot_record.id.startswith("record-config-runtime-effective-")
        assert snapshot_record.source_label == "Runtime config"
        assert snapshot_record.config_key == "runtime"
        assert snapshot_record.evidence_refs[0].kind == "config_snapshot"
        assert snapshot_record.evidence_refs[0].label == "Effective runtime config"

        change_record = records[1]
        assert change_record.id == f"record-config-runtime-change-{change.change_id}"
        assert change_record.config_key == "llm.default_model"
        assert change_record.severity == "info"
        assert change_record.evidence_refs[0].kind == "config_snapshot"
        assert "1 accepted key(s)" in change_record.summary
        assert raw_value not in change_record.model_dump_json()
        assert raw_value not in snapshot_record.model_dump_json()

        detail = _audit_record_detail(
            change_record,
            include_evidence=True,
            include_sanitized_payload=False,
        )
        assert detail.evidence[0].source == "config_store"
        assert raw_value not in detail.model_dump_json()

        effective_summary = provider.get_effective_config(session, records=records)
        assert effective_summary is not None
        assert effective_summary.profile_label == "Runtime config"
        assert effective_summary.settings_href == "/settings?tab=runtime"
        assert effective_summary.relevant_record_ids == tuple(record.id for record in records)


def _session(workspace_root: Path) -> Session:
    return Session(
        id="session-1",
        name="Runtime audit session",
        workspace_root=workspace_root,
        created_at=_ts(),
        last_active_at=_ts(),
    )


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config audit tests",
    )


def _ts() -> datetime:
    return datetime(2026, 6, 24, 14, 0, tzinfo=UTC)
