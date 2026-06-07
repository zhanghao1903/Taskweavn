"""Default UI command gateway orchestration."""

from __future__ import annotations

from taskweavn.server.ui_contract.command_mapping import (
    _child_idempotency_key,
    _command_bad_request_response,
    _command_exception_response,
    _command_not_found_response,
    _command_response,
    _guidance_mode,
    _merge_prompt_task_tree_results,
    _synthetic_task_tree_id,
    _task_node_patch,
    _TaskTreeIdentityError,
    _update_affected_scopes,
    _update_suggested_queries,
)
from taskweavn.server.ui_contract.commands import (
    AnswerAskPayload,
    AnswerAuthoringAskBatchPayload,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
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
from taskweavn.server.ui_contract.refs import (
    AffectedObjectImpact,
    AffectedObjectRef,
    AffectedScope,
    ObjectRef,
)
from taskweavn.task.ask_service import TaskAskCommandService
from taskweavn.task.authoring import RawTask
from taskweavn.task.collaborator_api import (
    CollaboratorApiAdapter,
    RawTaskAskAnswerSubmission,
)
from taskweavn.task.commands import CommandResult as CoreCommandResult
from taskweavn.task.commands import TaskCommandService
from taskweavn.task.models import TaskRef
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
    ) -> None:
        self._collaborator = collaborator
        self._task_commands = task_commands
        self._task_ref_resolver = task_ref_resolver
        self._authoring_state_store = authoring_state_store
        self._raw_task_store = raw_task_store
        self._ask_commands = ask_commands
        self._task_projection = task_projection

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
                if not self._raw_task_ready_for_planning(
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
                    raw_task = self._latest_raw_task(request.session_id)
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
            draft_tree_id = self._resolve_publish_draft_tree_id(request)
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
            if self._ask_commands is None:
                return _command_response(
                    request,
                    CoreCommandResult(
                        status="rejected",
                        message="ASK command service is not configured",
                    ),
                )
            result = self._ask_commands.answer_ask(
                request.session_id,
                ask_id,
                selected_option_ids=request.payload.selected_option_ids,
                text=request.payload.text,
                idempotency_key=request.idempotency_key,
                command_id=request.command_id,
            )
            return _ask_command_response(
                request,
                result,
                ask_id=ask_id,
                impact="changed",
                reason="ASK was answered.",
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def answer_authoring_ask_batch(
        self,
        raw_task_id: str,
        request: CommandRequest[AnswerAuthoringAskBatchPayload],
    ) -> CommandResponse:
        try:
            if self._authoring_context_is_superseded(request.session_id):
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
            if result.accepted and self._raw_task_all_asks_answered(
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

            if not self._session_has_published_task_tree(request.session_id):
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
            if self._ask_commands is None:
                return _command_response(
                    request,
                    CoreCommandResult(
                        status="rejected",
                        message="ASK command service is not configured",
                    ),
                )
            result = self._ask_commands.defer_ask(
                request.session_id,
                ask_id,
                reason=request.payload.reason,
                idempotency_key=request.idempotency_key,
                command_id=request.command_id,
            )
            return _ask_command_response(
                request,
                result,
                ask_id=ask_id,
                impact="changed",
                reason="ASK was deferred.",
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def cancel_ask(
        self,
        ask_id: str,
        request: CommandRequest[CancelAskPayload],
    ) -> CommandResponse:
        try:
            if self._ask_commands is None:
                return _command_response(
                    request,
                    CoreCommandResult(
                        status="rejected",
                        message="ASK command service is not configured",
                    ),
                )
            result = self._ask_commands.cancel_ask(
                request.session_id,
                ask_id,
                reason=request.payload.reason,
                idempotency_key=request.idempotency_key,
                command_id=request.command_id,
            )
            return _ask_command_response(
                request,
                result,
                ask_id=ask_id,
                impact="changed",
                reason="ASK was cancelled.",
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def _resolve_task_ref(self, session_id: str, task_node_id: str) -> TaskRef:
        return self._task_ref_resolver.resolve(session_id, task_node_id)

    def _latest_raw_task(self, session_id: str) -> RawTask | None:
        if self._raw_task_store is None:
            return None
        raw_tasks = self._raw_task_store.list_for_session(session_id)
        return raw_tasks[-1] if raw_tasks else None

    def _raw_task_ready_for_planning(self, session_id: str, raw_task_id: str) -> bool:
        if self._raw_task_store is None:
            return True
        raw_task = self._raw_task_store.get(session_id, raw_task_id)
        return raw_task is not None and raw_task.ready_for_planning

    def _raw_task_all_asks_answered(self, session_id: str, raw_task_id: str) -> bool:
        if self._raw_task_store is None:
            return False
        raw_task = self._raw_task_store.get(session_id, raw_task_id)
        if raw_task is None or not raw_task.asks:
            return False
        answered_ask_ids = {answer.ask_id for answer in raw_task.answers}
        return all(ask.ask_id in answered_ask_ids for ask in raw_task.asks)

    def _authoring_context_is_superseded(
        self,
        session_id: str,
    ) -> bool:
        if self._authoring_state_store is None:
            return self._session_has_published_task_tree(session_id)
        active = self._authoring_state_store.get_active(session_id)
        if active.active_state in {"draft_tree", "published", "cancelled"}:
            return True
        return active.active_state == "raw_task" and self._session_has_published_task_tree(
            session_id
        )

    def _session_has_published_task_tree(self, session_id: str) -> bool:
        if self._task_projection is None:
            return False
        try:
            tree = self._task_projection.list_task_tree(
                session_id,
                include_drafts=False,
                include_published=True,
            )
        except Exception:  # noqa: BLE001 - stale detection must not crash commands.
            return False
        return bool(tree.nodes)

    def _resolve_publish_draft_tree_id(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> str:
        provided = request.payload.task_tree_id
        if self._authoring_state_store is None:
            if provided is None:
                raise _TaskTreeIdentityError(
                    "publish requires a draft tree id when active authoring state is unavailable",
                    reason="missing_task_tree_identity",
                    session_id=request.session_id,
                )
            if provided == _synthetic_task_tree_id(request.session_id):
                raise _TaskTreeIdentityError(
                    "synthetic task tree id cannot be published without active authoring state",
                    reason="synthetic_task_tree_identity_unresolved",
                    session_id=request.session_id,
                    provided_task_tree_id=provided,
                )
            return provided

        active = self._authoring_state_store.get_active(request.session_id)
        active_id = active.active_draft_tree_id
        if (
            active.active_state == "published"
            and active_id is not None
            and request.idempotency_key is not None
            and provided in {None, active_id, _synthetic_task_tree_id(request.session_id)}
        ):
            return active_id
        if active.active_state != "draft_tree" or active_id is None:
            raise _TaskTreeIdentityError(
                "publish requires an active draft tree",
                reason="no_active_draft_tree",
                session_id=request.session_id,
                active_state=active.active_state,
            )

        if provided in {None, active_id, _synthetic_task_tree_id(request.session_id)}:
            return active_id

        raise _TaskTreeIdentityError(
            "publish draft tree identity does not match the active draft tree",
            reason="invalid_task_tree_identity",
            session_id=request.session_id,
            provided_task_tree_id=provided,
            active_draft_tree_id=active_id,
        )


def _ask_command_response[T](
    request: CommandRequest[T],
    result: CoreCommandResult,
    *,
    ask_id: str,
    impact: AffectedObjectImpact,
    reason: str,
) -> CommandResponse:
    ask_ref = ObjectRef(kind="ask", id=ask_id)
    return _command_response(
        request,
        result,
        object_refs=(ask_ref,),
        affected_objects=(
            AffectedObjectRef(
                ref=ask_ref,
                impact=impact,
                reason=reason,
            ),
        ),
        suggested_queries=("session.snapshot", "asks", "task.tree", "task.detail"),
        affected_scopes=(
            AffectedScope(kind="asks"),
            AffectedScope(kind="task_tree"),
            *(
                AffectedScope(kind="task_detail", task_ref=task_ref)
                for task_ref in result.affected_task_refs
            ),
        ),
    )
