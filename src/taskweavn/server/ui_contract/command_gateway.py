"""Default UI command gateway orchestration."""

from __future__ import annotations

from taskweavn.server.ui_contract.command_ask_helpers import (
    answer_ask_command,
    cancel_ask_command,
    defer_ask_command,
)
from taskweavn.server.ui_contract.command_authoring_helpers import (
    authoring_context_is_superseded,
    latest_raw_task,
    raw_task_all_asks_answered,
    raw_task_ready_for_planning,
    resolve_publish_draft_tree_id,
    session_has_published_task_tree,
)
from taskweavn.server.ui_contract.command_mapping import (
    _child_idempotency_key,
    _command_bad_request_response,
    _command_exception_response,
    _command_not_found_response,
    _command_response,
    _guidance_mode,
    _merge_prompt_task_tree_results,
    _plan_publish_command_result,
    _task_node_patch,
    _TaskTreeIdentityError,
    _update_affected_scopes,
    _update_suggested_queries,
)
from taskweavn.server.ui_contract.command_plan_helpers import (
    archived_legacy_plan_from_task_tree,
    archived_plan,
    is_legacy_plan_id,
    normalize_plan_id,
)
from taskweavn.server.ui_contract.commands import (
    AnswerAskPayload,
    AnswerAuthoringAskBatchPayload,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    ArchivePlanPayload,
    CancelAskPayload,
    DeferAskPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    RepairAuthoringStatePayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
    UpdateTaskNodePayload,
)
from taskweavn.server.ui_contract.envelopes import CommandRequest, CommandResponse
from taskweavn.server.ui_contract.gateway_protocols import TaskRefResolver
from taskweavn.server.ui_contract.mapping import map_task_tree_view
from taskweavn.server.ui_contract.refs import (
    AffectedObjectRef,
    AffectedScope,
    ObjectRef,
)
from taskweavn.task.ask_service import TaskAskCommandService
from taskweavn.task.collaborator_api import (
    CollaboratorApiAdapter,
    RawTaskAskAnswerSubmission,
)
from taskweavn.task.commands import CommandResult as CoreCommandResult
from taskweavn.task.commands import TaskCommandService
from taskweavn.task.models import TaskRef
from taskweavn.task.plan_commands import PlanLifecycleCommandService
from taskweavn.task.plan_models import Plan
from taskweavn.task.plan_publisher import PlanPublisher, PublishPlanCommand
from taskweavn.task.plan_stores import PlanStore
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore, RawTaskStore


class DefaultUiCommandGateway:
    """Default command gateway that wraps server-core command services."""

    def __init__(
        self,
        *,
        collaborator: CollaboratorApiAdapter,
        task_commands: TaskCommandService,
        task_ref_resolver: TaskRefResolver,
        authoring_state_store: AuthoringStateStore | None = None,
        raw_task_store: RawTaskStore | None = None,
        ask_commands: TaskAskCommandService | None = None,
        task_projection: TaskProjectionService | None = None,
        plan_store: PlanStore | None = None,
        plan_publisher: PlanPublisher | None = None,
        plan_lifecycle_commands: PlanLifecycleCommandService | None = None,
    ) -> None:
        self._collaborator = collaborator
        self._task_commands = task_commands
        self._task_ref_resolver = task_ref_resolver
        self._authoring_state_store = authoring_state_store
        self._raw_task_store = raw_task_store
        self._ask_commands = ask_commands
        self._task_projection = task_projection
        self._plan_store = plan_store
        self._plan_publisher = plan_publisher
        self._plan_lifecycle_commands = plan_lifecycle_commands

    def append_session_input(
        self,
        request: CommandRequest[AppendSessionInputPayload],
    ) -> CommandResponse:
        try:
            result = self._collaborator.append_session_message(
                session_id=request.session_id,
                content=request.payload.content,
                idempotency_key=request.idempotency_key,
            )
            return _command_response(
                request,
                result,
                suggested_queries=("session.snapshot", "session.messages", "task.tree"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="task_tree"),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def generate_task_tree(
        self,
        request: CommandRequest[GenerateTaskTreePayload],
    ) -> CommandResponse:
        try:
            object_refs: tuple[ObjectRef, ...] = ()
            affected_objects: tuple[AffectedObjectRef, ...] = ()
            if request.payload.raw_task_id is not None:
                if not raw_task_ready_for_planning(
                    self._raw_task_store,
                    request.session_id,
                    request.payload.raw_task_id,
                ):
                    result = CoreCommandResult(
                        status="rejected",
                        message=(
                            "RawTask requires authoring answers before task tree "
                            "generation"
                        ),
                    )
                    return _command_response(
                        request,
                        result,
                        object_refs=(
                            ObjectRef(kind="raw_task", id=request.payload.raw_task_id),
                        ),
                        suggested_queries=("session.snapshot", "session.messages"),
                        affected_scopes=(
                            AffectedScope(kind="session"),
                            AffectedScope(kind="messages"),
                        ),
                    )
                raw_ref = ObjectRef(kind="raw_task", id=request.payload.raw_task_id)
                object_refs = (raw_ref,)
                affected_objects = (
                    AffectedObjectRef(
                        ref=raw_ref,
                        impact="changed",
                        reason="TaskTree generation consumed this RawTask.",
                    ),
                )
                result = self._collaborator.generate_task_tree(
                    session_id=request.session_id,
                    raw_task_id=request.payload.raw_task_id,
                    idempotency_key=request.idempotency_key,
                )
            else:
                raw_result = self._collaborator.append_session_message(
                    session_id=request.session_id,
                    content=request.payload.prompt or "",
                    source_message_id=request.command_id,
                    idempotency_key=_child_idempotency_key(
                        request.idempotency_key,
                        "raw",
                    ),
                )
                if raw_result.accepted:
                    raw_task = latest_raw_task(
                        self._raw_task_store,
                        request.session_id,
                    )
                    if raw_task is not None and not raw_task.ready_for_planning:
                        result = raw_result
                    else:
                        tree_result = self._collaborator.generate_task_tree(
                            session_id=request.session_id,
                            raw_task_id=None,
                            idempotency_key=_child_idempotency_key(
                                request.idempotency_key,
                                "tree",
                            ),
                        )
                        result = _merge_prompt_task_tree_results(
                            raw_result,
                            tree_result,
                        )
                else:
                    result = raw_result
            return _command_response(
                request,
                result,
                object_refs=object_refs,
                affected_objects=affected_objects,
                suggested_queries=("session.snapshot", "task.tree", "session.messages"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="task_tree"),
                    AffectedScope(kind="messages"),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[UpdateTaskNodePayload],
    ) -> CommandResponse:
        try:
            task_ref = self._resolve_task_ref(request.session_id, task_node_id)
            result = self._task_commands.update_task_node(
                request.session_id,
                task_ref,
                _task_node_patch(request.payload),
                expected_version=request.expected_version,
            )
            return _command_response(
                request,
                result,
                suggested_queries=_update_suggested_queries(request.payload),
                affected_scopes=_update_affected_scopes(task_ref, request.payload),
            )
        except LookupError as exc:
            return _command_not_found_response(request, str(exc))
        except Exception as exc:
            return _command_exception_response(request, exc)

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[AppendTaskInputPayload],
    ) -> CommandResponse:
        try:
            task_ref = self._resolve_task_ref(request.session_id, task_node_id)
            if task_ref.kind == "draft":
                result = self._collaborator.append_task_message(
                    session_id=request.session_id,
                    task_ref=task_ref,
                    content=request.payload.content,
                )
            else:
                result = self._task_commands.append_task_message(
                    request.session_id,
                    task_ref,
                    request.payload.content,
                    mode=_guidance_mode(request.payload.mode),
                )
            return _command_response(
                request,
                result,
                suggested_queries=("session.snapshot", "session.messages", "task.detail"),
                affected_scopes=(
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="task_detail", task_ref=task_ref),
                ),
            )
        except LookupError as exc:
            return _command_not_found_response(request, str(exc))
        except Exception as exc:
            return _command_exception_response(request, exc)

    def publish_task_tree(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse:
        try:
            plan_response = self._publish_active_plan_if_available(request)
            if plan_response is not None:
                return plan_response

            draft_tree_id = resolve_publish_draft_tree_id(
                self._authoring_state_store,
                request,
            )
            tree_ref = ObjectRef(kind="draft_tree", id=draft_tree_id)
            result = self._collaborator.publish_task_tree(
                session_id=request.session_id,
                draft_tree_id=draft_tree_id,
                expected_version=request.expected_version,
                idempotency_key=request.idempotency_key,
                start_immediately=request.payload.start_immediately,
            )
            if result.accepted and self._authoring_state_store is not None:
                self._authoring_state_store.mark_published(
                    request.session_id,
                    draft_tree_id,
                )
            return _command_response(
                request,
                result,
                object_refs=(tree_ref,),
                affected_objects=(
                    AffectedObjectRef(
                        ref=tree_ref,
                        impact="changed",
                        reason="Draft tree publish was requested.",
                    ),
                ),
                suggested_queries=("session.snapshot", "task.tree"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="task_tree"),
                ),
            )
        except _TaskTreeIdentityError as exc:
            return _command_bad_request_response(request, str(exc), **exc.details)
        except Exception as exc:
            return _command_exception_response(request, exc)

    def _publish_active_plan_if_available(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse | None:
        plan = self._active_durable_plan(request.session_id)
        if plan is None or self._plan_publisher is None:
            return None

        result = self._plan_publisher.publish_plan(
            PublishPlanCommand(
                command_id=request.command_id,
                session_id=request.session_id,
                plan_id=plan.plan_id,
                expected_plan_version=request.expected_version,
                idempotency_key=request.idempotency_key or request.command_id,
            )
        )
        if (
            result.accepted
            and plan.source_draft_tree_id is not None
            and self._authoring_state_store is not None
        ):
            self._authoring_state_store.mark_published(
                request.session_id,
                plan.source_draft_tree_id,
            )
        plan_ref = ObjectRef(kind="plan", id=plan.plan_id)
        object_refs: tuple[ObjectRef, ...] = (plan_ref,)
        if plan.source_draft_tree_id is not None:
            object_refs = (
                ObjectRef(kind="draft_tree", id=plan.source_draft_tree_id),
                plan_ref,
            )
        return _command_response(
            request,
            _plan_publish_command_result(result),
            object_refs=object_refs,
            affected_objects=(
                AffectedObjectRef(
                    ref=plan_ref,
                    impact="changed",
                    reason="Durable Plan publish was requested.",
                ),
            ),
            suggested_queries=("session.snapshot", "task.tree"),
            affected_scopes=(
                AffectedScope(kind="session"),
                AffectedScope(kind="task_tree"),
            ),
        )

    def _active_durable_plan(self, session_id: str) -> Plan | None:
        if self._plan_store is None:
            return None
        if self._authoring_state_store is not None:
            active = self._authoring_state_store.get_active(session_id)
            if active.active_plan_id is not None:
                plan = self._plan_store.get_plan(session_id, active.active_plan_id)
                if plan is not None and not archived_plan(plan):
                    return plan
        plan = self._plan_store.get_active_plan(session_id)
        return None if archived_plan(plan) else plan

    def archive_plan(
        self,
        plan_id: str,
        request: CommandRequest[ArchivePlanPayload],
    ) -> CommandResponse:
        try:
            plan_id = normalize_plan_id(plan_id)
            if is_legacy_plan_id(request.session_id, plan_id):
                result = self._archive_legacy_plan(plan_id, request)
            else:
                if self._plan_lifecycle_commands is None:
                    return _command_response(
                        request,
                        CoreCommandResult(
                            status="rejected",
                            message="Plan lifecycle command service is not configured",
                        ),
                    )
                result = self._plan_lifecycle_commands.archive_plan(
                    request.session_id,
                    plan_id,
                    expected_version=request.expected_version,
                    reason=request.payload.reason,
                    request_id=request.command_id,
                )
            plan_ref = ObjectRef(kind="plan", id=plan_id)
            return _command_response(
                request,
                result,
                object_refs=(plan_ref,),
                affected_objects=(
                    AffectedObjectRef(
                        ref=plan_ref,
                        impact="changed",
                        reason="Plan archive was requested.",
                    ),
                ),
                suggested_queries=(
                    "session.snapshot",
                    "session.activity",
                    "task.tree",
                    "plans.history",
                ),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="task_tree"),
                    AffectedScope(kind="messages"),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def _archive_legacy_plan(
        self,
        plan_id: str,
        request: CommandRequest[ArchivePlanPayload],
    ) -> CoreCommandResult:
        if self._plan_store is None or self._task_projection is None:
            return CoreCommandResult(
                command_id=request.command_id,
                status="rejected",
                message="Legacy Plan archive requires PlanStore and TaskProjection",
            )
        existing = self._plan_store.get_plan(request.session_id, plan_id)
        if archived_plan(existing):
            return CoreCommandResult(
                command_id=request.command_id,
                status="accepted",
                message="Plan archived.",
            )
        if existing is not None:
            return CoreCommandResult(
                command_id=request.command_id,
                status="rejected",
                message="Legacy Plan archive conflicts with an active durable Plan",
            )

        source_tree = self._task_projection.list_task_tree(request.session_id)
        task_tree = map_task_tree_view(source_tree, tree_id=plan_id)
        if task_tree.status not in {"completed", "failed"}:
            return CoreCommandResult(
                command_id=request.command_id,
                status="rejected",
                message="only completed or failed legacy plans can be archived",
            )

        plan, nodes = archived_legacy_plan_from_task_tree(
            task_tree,
            expected_version=request.expected_version,
        )
        self._plan_store.create_plan(plan, nodes)
        if self._authoring_state_store is not None:
            self._authoring_state_store.cancel_active(request.session_id)
        return CoreCommandResult(
            command_id=request.command_id,
            status="accepted",
            message="Plan archived.",
        )

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[RetryTaskPayload],
    ) -> CommandResponse:
        try:
            task_ref = self._resolve_task_ref(request.session_id, task_node_id)
            if task_ref.kind != "published":
                result = CoreCommandResult(
                    status="rejected",
                    message="only published failed tasks can be retried",
                )
                return _command_response(request, result)
            result = self._task_commands.retry_task(
                request.session_id,
                task_ref.id,
                request.payload.instruction,
            )
            return _command_response(
                request,
                result,
                object_refs=(ObjectRef(kind="published_task", id=task_ref.id),),
                affected_objects=(
                    AffectedObjectRef(
                        ref=ObjectRef(kind="published_task", id=task_ref.id),
                        impact="changed",
                        reason="Manual retry moved this failed Task back to pending.",
                    ),
                ),
                suggested_queries=("session.snapshot", "task.tree", "task.detail"),
                affected_scopes=(
                    AffectedScope(kind="task_tree"),
                    AffectedScope(kind="task_detail", task_ref=task_ref),
                ),
            )
        except LookupError as exc:
            return _command_not_found_response(request, str(exc))
        except Exception as exc:
            return _command_exception_response(request, exc)

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[StopTaskPayload],
    ) -> CommandResponse:
        try:
            task_ref = self._resolve_task_ref(request.session_id, task_node_id)
            if task_ref.kind != "published":
                result = CoreCommandResult(
                    status="rejected",
                    message="only published pending or running tasks can be stopped",
                )
                return _command_response(request, result)
            result = self._task_commands.stop_task(
                request.session_id,
                task_ref.id,
                reason=request.payload.reason,
                request_id=request.command_id,
            )
            return _command_response(
                request,
                result,
                object_refs=(ObjectRef(kind="published_task", id=task_ref.id),),
                affected_objects=(
                    AffectedObjectRef(
                        ref=ObjectRef(kind="published_task", id=task_ref.id),
                        impact="changed",
                        reason="Stop intent was recorded for this Task.",
                    ),
                ),
                suggested_queries=("session.snapshot", "task.tree", "task.detail"),
                affected_scopes=(
                    AffectedScope(kind="task_tree"),
                    AffectedScope(kind="task_detail", task_ref=task_ref),
                    AffectedScope(kind="messages"),
                ),
            )
        except LookupError as exc:
            return _command_not_found_response(request, str(exc))
        except Exception as exc:
            return _command_exception_response(request, exc)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[ResolveConfirmationPayload],
    ) -> CommandResponse:
        try:
            result = self._task_commands.resolve_confirmation(
                request.session_id,
                confirmation_id,
                request.payload.value,
                note=request.payload.note,
            )
            confirmation_ref = ObjectRef(kind="message", id=confirmation_id)
            return _command_response(
                request,
                result,
                object_refs=(confirmation_ref,),
                affected_objects=(
                    AffectedObjectRef(
                        ref=confirmation_ref,
                        impact="changed",
                        reason="Confirmation was resolved.",
                    ),
                ),
                suggested_queries=(
                    "session.snapshot",
                    "session.messages",
                    "confirmations",
                    "task.detail",
                ),
                affected_scopes=(
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="confirmations"),
                    *(
                        AffectedScope(kind="task_detail", task_ref=task_ref)
                        for task_ref in result.affected_task_refs
                    ),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def answer_ask(
        self,
        ask_id: str,
        request: CommandRequest[AnswerAskPayload],
    ) -> CommandResponse:
        try:
            return answer_ask_command(self._ask_commands, ask_id, request)
        except Exception as exc:
            return _command_exception_response(request, exc)

    def answer_authoring_ask_batch(
        self,
        raw_task_id: str,
        request: CommandRequest[AnswerAuthoringAskBatchPayload],
    ) -> CommandResponse:
        try:
            if authoring_context_is_superseded(
                self._authoring_state_store,
                self._task_projection,
                request.session_id,
            ):
                raw_ref = ObjectRef(kind="raw_task", id=raw_task_id)
                ask_refs = tuple(
                    ObjectRef(kind="raw_task_ask", id=answer.ask_id)
                    for answer in request.payload.answers
                )
                result = CoreCommandResult(
                    status="rejected",
                    message=(
                        "stale_authoring_context: authoring ASK was superseded "
                        "by the active TaskTree"
                    ),
                )
                return _command_response(
                    request,
                    result,
                    object_refs=(raw_ref, *ask_refs),
                    affected_objects=(
                        AffectedObjectRef(
                            ref=raw_ref,
                            impact="superseded",
                            reason="stale_authoring_context",
                        ),
                        *(
                            AffectedObjectRef(
                                ref=ask_ref,
                                impact="superseded",
                                reason="stale_authoring_context",
                            )
                            for ask_ref in ask_refs
                        ),
                    ),
                    suggested_queries=(
                        "session.snapshot",
                        "session.messages",
                        "task.tree",
                    ),
                    affected_scopes=(
                        AffectedScope(kind="session"),
                        AffectedScope(kind="messages"),
                        AffectedScope(kind="task_tree"),
                    ),
                )
            result = self._collaborator.answer_raw_task_asks(
                session_id=request.session_id,
                raw_task_id=raw_task_id,
                answers=tuple(
                    RawTaskAskAnswerSubmission(
                        ask_id=answer.ask_id,
                        value=answer.value,
                    )
                    for answer in request.payload.answers
                ),
                idempotency_key=request.idempotency_key,
            )
            if result.accepted and raw_task_all_asks_answered(
                self._raw_task_store,
                request.session_id,
                raw_task_id,
            ):
                tree_result = self._collaborator.generate_task_tree(
                    session_id=request.session_id,
                    raw_task_id=raw_task_id,
                    idempotency_key=_child_idempotency_key(
                        request.idempotency_key,
                        "tree",
                    ),
                )
                result = _merge_prompt_task_tree_results(result, tree_result)
            raw_ref = ObjectRef(kind="raw_task", id=raw_task_id)
            ask_refs = tuple(
                ObjectRef(kind="raw_task_ask", id=answer.ask_id)
                for answer in request.payload.answers
            )
            return _command_response(
                request,
                result,
                object_refs=(raw_ref, *ask_refs),
                affected_objects=(
                    AffectedObjectRef(
                        ref=raw_ref,
                        impact="changed",
                        reason="RawTask authoring ASK answers were submitted.",
                    ),
                    *(
                        AffectedObjectRef(
                            ref=ask_ref,
                            impact="changed",
                            reason="RawTask authoring ASK was answered.",
                        )
                        for ask_ref in ask_refs
                    ),
                ),
                suggested_queries=("session.snapshot", "session.messages", "task.tree"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="task_tree"),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def repair_authoring_state(
        self,
        request: CommandRequest[RepairAuthoringStatePayload],
    ) -> CommandResponse:
        try:
            if self._authoring_state_store is None:
                result = CoreCommandResult(
                    status="rejected",
                    message="authoring state store is not configured",
                )
                return _command_response(request, result)

            active = self._authoring_state_store.get_active(request.session_id)
            if active.active_state != "raw_task" or active.active_raw_task_id is None:
                result = CoreCommandResult(
                    status="rejected",
                    message="no active raw authoring state requires repair",
                )
                return _command_response(request, result)

            if not session_has_published_task_tree(
                self._task_projection,
                request.session_id,
            ):
                result = CoreCommandResult(
                    status="rejected",
                    message="authoring state repair requires an existing TaskTree",
                )
                return _command_response(request, result)

            raw_ref = ObjectRef(kind="raw_task", id=active.active_raw_task_id)
            self._authoring_state_store.cancel_active(request.session_id)
            result = CoreCommandResult(
                status="accepted",
                message="dirty authoring state repaired; active authoring flow closed",
            )
            return _command_response(
                request,
                result,
                object_refs=(raw_ref,),
                affected_objects=(
                    AffectedObjectRef(
                        ref=raw_ref,
                        impact="superseded",
                        reason=request.payload.reason,
                    ),
                ),
                suggested_queries=("session.snapshot", "session.messages", "task.tree"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="task_tree"),
                    AffectedScope(kind="asks"),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def defer_ask(
        self,
        ask_id: str,
        request: CommandRequest[DeferAskPayload],
    ) -> CommandResponse:
        try:
            return defer_ask_command(self._ask_commands, ask_id, request)
        except Exception as exc:
            return _command_exception_response(request, exc)

    def cancel_ask(
        self,
        ask_id: str,
        request: CommandRequest[CancelAskPayload],
    ) -> CommandResponse:
        try:
            return cancel_ask_command(self._ask_commands, ask_id, request)
        except Exception as exc:
            return _command_exception_response(request, exc)

    def _resolve_task_ref(self, session_id: str, task_node_id: str) -> TaskRef:
        return self._task_ref_resolver.resolve(session_id, task_node_id)
