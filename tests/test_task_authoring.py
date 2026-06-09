"""Tests for Collaborator Agent authoring contracts and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    ActorRef,
    AuthoringCommandBatch,
    AuthoringCommandError,
    AuthoringCommandResult,
    AuthoringContext,
    AuthoringMessageEffect,
    CapabilityCatalog,
    CapabilityDescriptor,
    DraftTaskNode,
    DraftTaskNodeProposal,
    DraftTaskPatchProposal,
    DraftTaskTree,
    DraftTaskTreeOperation,
    DraftTaskTreeProposal,
    DraftTaskTreeValidator,
    FeasibilityReport,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    PlanProposal,
    PlanTaskNodeProposal,
    PublishDraftTaskTreeCommand,
    RawTask,
    RawTaskAnswer,
    RawTaskAnswerOption,
    RawTaskAsk,
    RawTaskOperation,
    StaticCapabilityCatalog,
    TaskNodeOption,
    TaskNodeOptionSet,
    TaskNodePatch,
    TaskRef,
)


def _catalog() -> StaticCapabilityCatalog:
    return StaticCapabilityCatalog(["general", "writing", "testing", "writing"])


def _actor() -> ActorRef:
    return ActorRef(actor_id="collab", kind="collaborator", display_name="Collaborator")


def _ready_feasibility() -> FeasibilityReport:
    return FeasibilityReport(
        status="ready",
        confidence=0.9,
        reasons=("enough context to draft",),
        required_capabilities=("writing",),
    )


def _root(
    *,
    capability: str = "writing",
    status: str = "draft",
    title: str = "Draft release note",
    intent: str = "Prepare release notes",
) -> DraftTaskNode:
    return DraftTaskNode(
        draft_task_id="d1",
        session_id="s1",
        draft_tree_id="tree1",
        title=title,
        intent=intent,
        required_capability=capability,
        status=status,  # type: ignore[arg-type]
    )


def _tree(root: DraftTaskNode | None = None) -> DraftTaskTree:
    return DraftTaskTree(
        draft_tree_id="tree1",
        session_id="s1",
        root_nodes=(root or _root(),),
    )


def test_feasibility_report_defaults_next_action() -> None:
    ready = _ready_feasibility()
    ask = FeasibilityReport(
        status="needs_clarification",
        confidence=0.7,
        missing_inputs=("target audience",),
    )
    unsafe = FeasibilityReport(
        status="unsafe",
        confidence=0.95,
        reasons=("unsafe request",),
    )

    assert ready.suggested_next_action == "generate_task_tree"
    assert ask.suggested_next_action == "ask_user"
    assert unsafe.suggested_next_action == "decline"


def test_feasibility_report_validates_bounds_and_payload() -> None:
    with pytest.raises(ValidationError):
        FeasibilityReport(status="ready", confidence=1.5)
    with pytest.raises(ValidationError, match="requires missing inputs or permissions"):
        FeasibilityReport(status="needs_clarification", confidence=0.5)
    with pytest.raises(ValidationError, match="ready feasibility"):
        FeasibilityReport(
            status="ready",
            confidence=0.8,
            suggested_next_action="ask_user",
        )


def test_raw_task_defaults_and_ready_state() -> None:
    task = RawTask(
        session_id="s1",
        source_message_id="m1",
        user_input="Build me a course website",
    )
    ready = RawTask(
        session_id="s1",
        source_message_id="m1",
        user_input="Build me a course website",
        status="ready_to_plan",
        feasibility=_ready_feasibility(),
        intent_summary="Build a course website",
    )

    assert task.status == "created"
    assert not task.ready_for_planning
    assert ready.ready_for_planning
    assert ready.version == 1
    with pytest.raises(ValidationError):
        ready.status = "converted"


def test_raw_task_awaiting_user_requires_unanswered_ask() -> None:
    with pytest.raises(ValidationError, match="unanswered ask"):
        RawTask(
            session_id="s1",
            source_message_id="m1",
            user_input="Build something",
            status="awaiting_user",
        )


def test_raw_task_tracks_required_unanswered_asks() -> None:
    ask = RawTaskAsk(
        ask_id="ask1",
        raw_task_id="raw1",
        question="What audience should this target?",
        options=(
            RawTaskAnswerOption(label="Beginners", value="beginners"),
            RawTaskAnswerOption(label="Advanced", value="advanced"),
        ),
        reason="audience changes task shape",
    )
    task = RawTask(
        raw_task_id="raw1",
        session_id="s1",
        source_message_id="m1",
        user_input="Make courseware",
        status="awaiting_user",
        asks=(ask,),
    )
    answered = RawTask(
        raw_task_id="raw1",
        session_id="s1",
        source_message_id="m1",
        user_input="Make courseware",
        asks=(ask,),
        answers=(
            RawTaskAnswer(
                raw_task_id="raw1",
                ask_id="ask1",
                value="beginners",
                source_message_id="m2",
            ),
        ),
    )

    assert task.unanswered_ask_ids == ("ask1",)
    assert answered.unanswered_ask_ids == ()


def test_raw_task_validates_ask_and_answer_identity() -> None:
    ask = RawTaskAsk(
        ask_id="ask1",
        raw_task_id="other",
        question="Missing?",
        reason="test",
    )
    with pytest.raises(ValidationError, match="RawTaskAsk raw_task_id"):
        RawTask(
            raw_task_id="raw1",
            session_id="s1",
            source_message_id="m1",
            user_input="Do this",
            asks=(ask,),
        )

    with pytest.raises(ValidationError, match="existing RawTaskAsk"):
        RawTask(
            raw_task_id="raw1",
            session_id="s1",
            source_message_id="m1",
            user_input="Do this",
            answers=(
                RawTaskAnswer(
                    raw_task_id="raw1",
                    ask_id="missing",
                    value="answer",
                    source_message_id="m2",
                ),
            ),
        )


def test_raw_task_ready_to_plan_requires_ready_feasibility() -> None:
    with pytest.raises(ValidationError, match="requires feasibility"):
        RawTask(
            session_id="s1",
            source_message_id="m1",
            user_input="Do this",
            status="ready_to_plan",
        )
    with pytest.raises(ValidationError, match="requires ready feasibility"):
        RawTask(
            session_id="s1",
            source_message_id="m1",
            user_input="Do this",
            status="ready_to_plan",
            feasibility=FeasibilityReport(
                status="needs_clarification",
                confidence=0.4,
                missing_inputs=("scope",),
            ),
        )


def test_raw_task_rejected_requires_terminal_feasibility_when_present() -> None:
    unsafe = RawTask(
        session_id="s1",
        source_message_id="m1",
        user_input="Unsafe request",
        status="rejected",
        feasibility=FeasibilityReport(
            status="unsafe",
            confidence=0.95,
            reasons=("unsafe",),
        ),
    )

    assert unsafe.status == "rejected"
    with pytest.raises(ValidationError, match="unsupported or unsafe"):
        RawTask(
            session_id="s1",
            source_message_id="m1",
            user_input="Ambiguous request",
            status="rejected",
            feasibility=FeasibilityReport(
                status="needs_clarification",
                confidence=0.4,
                missing_inputs=("scope",),
            ),
        )


def test_static_capability_catalog_strips_empty_and_duplicates() -> None:
    catalog = StaticCapabilityCatalog(
        [
            " writing ",
            "",
            CapabilityDescriptor(
                capability_id="testing",
                display_name="Testing",
                summary="Run and write tests",
                applicable_domains=("quality",),
            ),
            "writing",
        ]
    )

    assert tuple(capability.capability_id for capability in catalog.all()) == (
        "writing",
        "testing",
    )
    testing = catalog.get("testing")
    assert testing is not None
    assert testing.display_name == "Testing"
    assert catalog.contains(" writing ")
    assert not catalog.contains("unknown")
    assert catalog.query("write tests")[0].capability_id == "testing"
    assert catalog.query("anything", domains=("quality",))[0].capability_id == "testing"
    assert isinstance(catalog, CapabilityCatalog)


def test_authoring_context_requires_selected_ref_for_task_mode() -> None:
    with pytest.raises(ValidationError, match="selected_task_ref"):
        AuthoringContext(session_id="s1", mode="task")


def test_authoring_context_validates_selected_node_matches_ref() -> None:
    node = _root()
    context = AuthoringContext(
        session_id="s1",
        mode="task",
        selected_task_ref=TaskRef.draft("d1"),
        selected_node=node,
        recent_messages=(
            AgentMessage(
                session_id="s1",
                task_id="d1",
                message_type="informational",
                content="Make it safer",
            ),
        ),
    )

    assert context.selected_node is node
    assert context.recent_messages[0].task_id == "d1"


def test_authoring_context_rejects_mismatched_selected_node() -> None:
    with pytest.raises(ValidationError, match="selected_node"):
        AuthoringContext(
            session_id="s1",
            mode="task",
            selected_task_ref=TaskRef.draft("other"),
            selected_node=_root(),
        )


def test_draft_task_tree_proposal_supports_nested_nodes() -> None:
    proposal = DraftTaskTreeProposal(
        assistant_message="I drafted a safe release workflow.",
        roots=(
            DraftTaskNodeProposal(
                title="Prepare release",
                intent="Prepare release notes",
                required_capability="writing",
                children=(
                    DraftTaskNodeProposal(
                        title="Run checks",
                        intent="Run regression tests",
                        required_capability="testing",
                    ),
                ),
            ),
        ),
    )

    assert proposal.roots[0].children[0].title == "Run checks"
    with pytest.raises(ValidationError):
        proposal.roots = ()


def test_plan_proposal_is_flat_plan_plus_tasknodes_contract() -> None:
    proposal = PlanProposal(
        title="Release plan",
        summary="Prepare the release safely.",
        assistant_message="Drafted a flat plan.",
        tasks=(
            PlanTaskNodeProposal(
                client_task_id="write-notes",
                task_index=1,
                title="Write notes",
                intent="Prepare release notes",
                required_capability="writing",
            ),
            PlanTaskNodeProposal(
                client_task_id="run-checks",
                task_index=2,
                title="Run checks",
                intent="Run regression tests",
                required_capability="testing",
                depends_on=("write-notes",),
            ),
        ),
    )

    assert proposal.schema_version == "plato.plan.proposal.v1"
    assert [task.task_index for task in proposal.tasks] == [1, 2]
    assert proposal.tasks[1].depends_on == ("write-notes",)


def test_plan_proposal_rejects_hierarchy_and_role_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PlanProposal.model_validate(
            {
                "title": "Nested plan",
                "assistant_message": "Drafted a nested plan.",
                "tasks": [
                    {
                        "task_index": 1,
                        "title": "Parent",
                        "intent": "Do parent work",
                        "required_capability": "writing",
                        "children": [],
                        "node_type": "summary",
                        "execution_role": "aggregate_only",
                        "children_policy": "all_done",
                    }
                ],
            }
        )

    message = str(exc_info.value)
    assert "children" in message
    assert "node_type" in message
    assert "execution_role" in message
    assert "children_policy" in message


def test_plan_proposal_requires_unique_task_indexes_and_client_ids() -> None:
    duplicated_task = {
        "client_task_id": "same",
        "task_index": 1,
        "title": "Write notes",
        "intent": "Prepare release notes",
        "required_capability": "writing",
    }

    with pytest.raises(ValidationError, match="task_index"):
        PlanProposal.model_validate(
            {
                "title": "Release plan",
                "assistant_message": "Drafted a flat plan.",
                "tasks": [duplicated_task, {**duplicated_task, "client_task_id": "b"}],
            }
        )
    with pytest.raises(ValidationError, match="client_task_id"):
        PlanProposal.model_validate(
            {
                "title": "Release plan",
                "assistant_message": "Drafted a flat plan.",
                "tasks": [duplicated_task, {**duplicated_task, "task_index": 2}],
            }
        )


def test_task_node_option_requires_patch_or_message() -> None:
    option = TaskNodeOption(
        label="Add test constraint",
        patch=TaskNodePatch(constraints_add=("must run pytest",)),
    )
    option_set = TaskNodeOptionSet(
        session_id="s1",
        task_ref=TaskRef.draft("d1"),
        options=(option,),
    )

    assert option_set.options[0].patch is not None
    with pytest.raises(ValidationError, match="patch or message"):
        TaskNodeOption(label="No effect")


def test_patch_proposal_and_authoring_result_are_frozen() -> None:
    proposal = DraftTaskPatchProposal(
        patch=TaskNodePatch(intent="Add release notes and smoke checks"),
        assistant_message="I will tighten the task.",
    )
    result = AuthoringCommandResult(
        ok=True,
        object_refs=(TaskRef.draft("d1"),),
    )

    assert proposal.affected_scope == "selected_node"
    assert result.accepted
    assert result.status == "accepted"
    with pytest.raises(ValidationError):
        result.ok = False


def test_mutate_raw_task_command_allows_create_without_id() -> None:
    command = MutateRawTaskCommand(
        session_id="s1",
        actor=_actor(),
        operations=(
            RawTaskOperation(
                op="create",
                payload={"source_message_id": "m1", "user_input": "Make a website"},
            ),
        ),
    )

    assert command.raw_task_id is None
    assert command.operations[0].op == "create"


def test_mutate_raw_task_command_requires_target_for_non_create() -> None:
    with pytest.raises(ValidationError, match="requires raw_task_id"):
        MutateRawTaskCommand(
            session_id="s1",
            actor=_actor(),
            operations=(RawTaskOperation(op="set_status", payload={"status": "cancelled"}),),
        )


def test_mutate_draft_tree_command_requires_target_for_non_create() -> None:
    with pytest.raises(ValidationError, match="requires draft_tree_id"):
        MutateDraftTaskTreeCommand(
            session_id="s1",
            actor=_actor(),
            operations=(DraftTaskTreeOperation(op="mark_accepted"),),
        )

    command = MutateDraftTaskTreeCommand(
        session_id="s1",
        raw_task_id="raw1",
        actor=_actor(),
        operations=(DraftTaskTreeOperation(op="create_tree", payload={"roots": []}),),
    )

    assert command.draft_tree_id is None


def test_publish_command_requires_idempotency_key() -> None:
    command = PublishDraftTaskTreeCommand(
        session_id="s1",
        draft_tree_id="tree1",
        actor=_actor(),
        idempotency_key="publish-tree1",
    )

    assert command.publish_options.start_immediately
    with pytest.raises(ValidationError):
        PublishDraftTaskTreeCommand(
            session_id="s1",
            draft_tree_id="tree1",
            actor=_actor(),
            idempotency_key="",
        )


def test_authoring_command_batch_validates_session_and_actor() -> None:
    actor = _actor()
    command = MutateRawTaskCommand(
        session_id="s1",
        actor=actor,
        raw_task_id="raw1",
        operations=(RawTaskOperation(op="set_status", payload={"status": "cancelled"}),),
    )
    batch = AuthoringCommandBatch(session_id="s1", actor=actor, commands=(command,))

    assert batch.mode == "all_or_nothing"
    with pytest.raises(ValidationError, match="session_id"):
        AuthoringCommandBatch(session_id="other", actor=actor, commands=(command,))
    with pytest.raises(ValidationError, match="actor"):
        AuthoringCommandBatch(
            session_id="s1",
            actor=ActorRef(actor_id="other", kind="collaborator"),
            commands=(command,),
        )


def test_authoring_command_batch_rejects_best_effort_publish() -> None:
    actor = _actor()
    command = PublishDraftTaskTreeCommand(
        session_id="s1",
        draft_tree_id="tree1",
        actor=actor,
        idempotency_key="publish-tree1",
    )

    with pytest.raises(ValidationError, match="all_or_nothing"):
        AuthoringCommandBatch(
            session_id="s1",
            actor=actor,
            mode="best_effort",
            commands=(command,),
        )


def test_authoring_message_effect_requires_actionable_options() -> None:
    effect = AuthoringMessageEffect(
        message_type="actionable",
        content="Choose an audience",
        action_options=("beginner", "advanced"),
        requires_response=True,
    )

    assert effect.requires_response
    with pytest.raises(ValidationError, match="must be actionable"):
        AuthoringMessageEffect(
            message_type="informational",
            content="FYI",
            requires_response=True,
        )
    with pytest.raises(ValidationError, match="action_options"):
        AuthoringMessageEffect(
            message_type="actionable",
            content="Choose",
            requires_response=True,
        )


def test_authoring_command_result_validates_error_shape() -> None:
    accepted = AuthoringCommandResult(ok=True, applied_command_ids=("c1",))
    rejected = AuthoringCommandResult(
        ok=False,
        errors=(AuthoringCommandError(code="invalid_transition", message="cannot publish"),),
    )

    assert accepted.status == "accepted"
    assert rejected.status == "rejected"
    with pytest.raises(ValidationError, match="must not include errors"):
        AuthoringCommandResult(
            ok=True,
            errors=(AuthoringCommandError(code="bad", message="bad"),),
        )
    with pytest.raises(ValidationError, match="requires errors"):
        AuthoringCommandResult(ok=False)


def test_validator_accepts_valid_tree() -> None:
    validation = DraftTaskTreeValidator(capability_catalog=_catalog()).validate_tree(_tree())

    assert validation.valid
    assert validation.errors == ()
    assert validation.model_dump()["valid"] is True


def test_validator_rejects_unknown_capability() -> None:
    validation = DraftTaskTreeValidator(capability_catalog=_catalog()).validate_tree(
        _tree(_root(capability="imaginary")),
    )

    assert not validation.valid
    assert validation.errors[0].code == "unknown_capability"
    assert validation.errors[0].draft_task_id == "d1"


def test_validator_rejects_cancelled_node_before_publish() -> None:
    validation = DraftTaskTreeValidator(capability_catalog=_catalog()).validate_tree(
        _tree(_root(status="cancelled")),
    )

    assert not validation.valid
    assert validation.errors[0].code == "status_not_publishable"


def test_validator_warns_when_node_count_reaches_limit() -> None:
    validation = DraftTaskTreeValidator(
        capability_catalog=_catalog(),
        max_nodes=1,
    ).validate_tree(_tree())

    assert validation.valid
    assert validation.warnings[0].code == "node_count_near_limit"


def test_validator_checks_nested_proposal_capabilities_and_depth() -> None:
    proposal = DraftTaskTreeProposal(
        assistant_message="Drafted.",
        roots=(
            DraftTaskNodeProposal(
                title="Root",
                intent="Root intent",
                required_capability="general",
                children=(
                    DraftTaskNodeProposal(
                        title="Child",
                        intent="Child intent",
                        required_capability="unknown",
                    ),
                ),
            ),
        ),
    )

    validation = DraftTaskTreeValidator(
        capability_catalog=_catalog(),
        max_depth=1,
    ).validate_proposal(proposal)

    assert not validation.valid
    assert {issue.code for issue in validation.errors} == {
        "max_depth_exceeded",
        "unknown_capability",
    }


def test_validator_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError, match="max_depth"):
        DraftTaskTreeValidator(capability_catalog=_catalog(), max_depth=0)
    with pytest.raises(ValueError, match="max_nodes"):
        DraftTaskTreeValidator(capability_catalog=_catalog(), max_nodes=0)
