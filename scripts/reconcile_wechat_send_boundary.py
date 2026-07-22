"""Offline reconciliation for one manually verified ambiguous WeChat send."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from taskweavn.integrations.wechat_tool import (
    SendBoundaryReconciliationEvidence,
    SendBoundaryStoreError,
    SqliteSendBoundaryStore,
    managed_send_boundary_key,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mark one unknown WeChat send boundary completed from explicit "
            "read-only UI evidence. This command never connects to WeChat or Helper."
        )
    )
    parser.add_argument("--effect-db", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--request-hash", required=True)
    parser.add_argument("--contact", required=True)
    parser.add_argument("--message-sha256", required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--confirm-exact-outgoing-count", type=int, required=True)
    parser.add_argument("--confirm-chat-input-empty", action="store_true")
    parser.add_argument("--confirm-reconciliation", required=True)
    parser.add_argument("--evidence-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = reconcile(args)
    except (SendBoundaryStoreError, ValueError) as exc:
        print(f"reconciliation refused: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.evidence_output is not None:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def reconcile(args: argparse.Namespace) -> dict[str, object]:
    if args.confirm_reconciliation != "COMPLETE":
        raise ValueError("--confirm-reconciliation must be COMPLETE")
    if not args.confirm_chat_input_empty:
        raise ValueError("--confirm-chat-input-empty is required")
    if not args.effect_db.is_file():
        raise ValueError(f"effect database does not exist: {args.effect_db}")

    observed_at = datetime.fromisoformat(args.observed_at.replace("Z", "+00:00"))
    evidence = SendBoundaryReconciliationEvidence(
        source="manual_read_only_ui",
        operator=args.operator,
        expected_contact=args.contact,
        message_sha256=args.message_sha256,
        observed_outgoing_count=args.confirm_exact_outgoing_count,
        exact_message_visible=True,
        chat_input_empty=True,
        observed_at=observed_at,
        note=args.note,
    )
    key = managed_send_boundary_key(args.session_id, args.task_id)
    with SqliteSendBoundaryStore(args.effect_db) as store:
        before = store.get(scope_id=args.session_id, idempotency_key=key)
        if before is None:
            raise SendBoundaryStoreError("managed send boundary does not exist")
        original_observation_hash = _observation_hash(before.observation)
        record = store.reconcile_unknown_to_completed(
            scope_id=args.session_id,
            idempotency_key=key,
            request_hash=args.request_hash,
            evidence=evidence,
        )
        after = store.get(scope_id=args.session_id, idempotency_key=key)
    if after is None or after.reconciliation is None or after.reconciled_at is None:
        raise SendBoundaryStoreError("reconciled boundary could not be read back")
    if _observation_hash(after.observation) != original_observation_hash:
        raise SendBoundaryStoreError("original send observation changed during reconciliation")

    return {
        "schema": "plato.wechat_send_boundary.reconciliation.v1",
        "effectDb": str(args.effect_db),
        "scopeId": record.scope_id,
        "idempotencyKeyHash": _sha256(record.idempotency_key),
        "requestHash": record.request_hash,
        "previousState": before.state,
        "state": after.state,
        "originalObservationHash": original_observation_hash,
        "reconciledAt": after.reconciled_at.isoformat(),
        "evidence": {
            "source": after.reconciliation.source,
            "operator": after.reconciliation.operator,
            "contactHash": _sha256(after.reconciliation.expected_contact),
            "messageSha256": after.reconciliation.message_sha256.removeprefix("sha256:"),
            "observedOutgoingCount": after.reconciliation.observed_outgoing_count,
            "exactMessageVisible": after.reconciliation.exact_message_visible,
            "chatInputEmpty": after.reconciliation.chat_input_empty,
            "observedAt": after.reconciliation.observed_at.isoformat(),
            "note": after.reconciliation.note,
        },
        "externalActionAttempted": False,
    }


def _observation_hash(observation: object | None) -> str:
    if observation is None:
        return _sha256("null")
    model_dump_json = getattr(observation, "model_dump_json", None)
    if not callable(model_dump_json):
        raise ValueError("send boundary observation is not serializable")
    return _sha256(str(model_dump_json()))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
