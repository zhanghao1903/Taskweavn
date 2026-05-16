"""Tests for publish-time Pipeline Task expansion."""

from __future__ import annotations

from taskweavn.task import (
    DefaultPipelineTaskLoader,
    DefaultTaskPublisher,
    InMemoryPublishIdempotencyStore,
    InMemoryTaskBus,
    NormalizedTaskNode,
    NormalizedTaskTree,
    PipelineConfig,
    PipelineTaskLoader,
    PipelineTaskSpec,
    PublisherRef,
    PublishRequest,
    PublishSource,
    TaskDomain,
    TaskPublishOptions,
    TaskPublishService,
)


def test_pipeline_loader_protocol_conformance() -> None:
    loader = DefaultPipelineTaskLoader(_pipeline_config())

    assert isinstance(loader, PipelineTaskLoader)


def test_pipeline_loader_expands_before_and_begin_roots() -> None:
    request = _request()
    loader = DefaultPipelineTaskLoader(_pipeline_config())

    expanded = loader.expand_for_publish(request)

    assert expanded.task_tree is not None
    assert expanded.task_tree.root_ids == (
        "pipeline:task_before:review",
        "pipeline:task_begin:prepare",
        "main",
    )
    assert expanded.task_tree.task_count == 3
    assert expanded.task_tree.metadata["pipeline_enabled"] is True
    assert expanded.task_tree.metadata["pipeline_task_count"] == 2


def test_pipeline_loader_does_not_load_after_tasks_at_publish_time() -> None:
    request = _request()
    loader = DefaultPipelineTaskLoader(
        PipelineConfig(
            task_after=(
                PipelineTaskSpec(
                    id="summary",
                    title="Summary",
                    intent_template="Summarize after completion",
                    required_capability="summarize",
                ),
            )
        )
    )

    expanded = loader.expand_for_publish(request)

    assert expanded == request


def test_pipeline_loader_respects_allow_pipeline_false() -> None:
    request = _request(options=TaskPublishOptions(allow_pipeline=False))
    loader = DefaultPipelineTaskLoader(_pipeline_config())

    expanded = loader.expand_for_publish(request)

    assert expanded == request


def test_task_publish_service_preview_includes_pipeline_tasks_without_writing_bus() -> None:
    bus = InMemoryTaskBus()
    service = _service(bus)

    preview = service.preview(_request())

    assert preview.ok
    assert preview.task_count == 3
    assert bus.list_for_session("s1") == []


def test_task_publish_service_publishes_pipeline_tasks_as_ordinary_tasks() -> None:
    bus = InMemoryTaskBus()
    service = _service(bus)

    result = service.publish(_request())
    tasks = bus.list_for_session("s1")
    task_by_title = _tasks_by_title(tasks)

    assert result.accepted
    assert len(tasks) == 3
    assert task_by_title["Review"].status == "pending"
    assert task_by_title["Prepare"].status == "pending"
    assert task_by_title["Main"].status == "pending"
    review_metadata = _metadata(task_by_title["Review"])
    main_metadata = _metadata(task_by_title["Main"])
    assert review_metadata["source"] == "pipeline"
    assert review_metadata["pipeline_stage"] == "task_before"
    assert review_metadata["pipeline_spec_id"] == "review"
    assert review_metadata["pipeline_source_request_id"] == "req-1"
    assert main_metadata["source_node_id"] == "main"


def test_pipeline_can_be_disabled_by_config() -> None:
    bus = InMemoryTaskBus()
    loader = DefaultPipelineTaskLoader(_pipeline_config(enabled=False))
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        idempotency_store=InMemoryPublishIdempotencyStore(),
        pipeline_loader=loader,
    )

    result = service.publish(_request())

    assert result.accepted
    assert len(bus.list_for_session("s1")) == 1


def test_pipeline_expansion_failure_returns_skipped_result() -> None:
    bus = InMemoryTaskBus()
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        pipeline_loader=_BrokenPipelineLoader(),
    )

    preview = service.preview(_request())
    result = service.publish(_request())

    assert not preview.ok
    assert preview.errors == ("pipeline expansion failed",)
    assert result.skipped
    assert result.reason == "pipeline expansion failed"
    assert bus.list_for_session("s1") == []


class _BrokenPipelineLoader:
    def expand_for_publish(self, request: PublishRequest) -> PublishRequest:  # noqa: ARG002
        raise RuntimeError("template error")


def _service(bus: InMemoryTaskBus) -> TaskPublishService:
    return TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        idempotency_store=InMemoryPublishIdempotencyStore(),
        pipeline_loader=DefaultPipelineTaskLoader(_pipeline_config()),
    )


def _pipeline_config(*, enabled: bool = True) -> PipelineConfig:
    return PipelineConfig(
        enabled=enabled,
        task_before=(
            PipelineTaskSpec(
                id="review",
                title="Review",
                intent_template="Review request {request_id} with roots {root_ids}",
                required_capability="audit",
                agent_ref="agent.audit",
                order=0,
            ),
        ),
        task_begin=(
            PipelineTaskSpec(
                id="prepare",
                title="Prepare",
                intent_template="Prepare session {session_id} before {task_count} tasks",
                required_capability="summarize",
                agent_ref="agent.summary",
                order=1,
            ),
        ),
    )


def _request(
    *,
    options: TaskPublishOptions | None = None,
) -> PublishRequest:
    publisher = PublisherRef(kind="custom_tree", actor_id="user-1")
    tree = NormalizedTaskTree(
        root_nodes=(
            NormalizedTaskNode(
                node_id="main",
                title="Main",
                intent="Do main work",
                required_capability="general",
            ),
        ),
        source=publisher,
        source_ref="custom-tree-1",
    )
    return PublishRequest(
        request_id="req-1",
        session_id="s1",
        publisher=publisher,
        source=PublishSource(source_type="custom_tree", source_id="custom-tree-1"),
        task_tree=tree,
        options=options or TaskPublishOptions(),
        idempotency_key="publish-1",
    )


def _tasks_by_title(tasks: list[TaskDomain]) -> dict[str, TaskDomain]:
    return {str(_metadata(task)["title"]): task for task in tasks}


def _metadata(task: TaskDomain) -> dict[str, object]:
    assert task.dispatch_constraints is not None
    return task.dispatch_constraints.metadata
