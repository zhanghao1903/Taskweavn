# Product 1.1 Skill Governance Technical Design

> Status: implemented backend foundation on branch
>
> Last Updated: 2026-06-11
>
> Feature Plan:
> [Product 1.1 Skill Governance Plan](product-1-1-skill-governance.md)
>
> Research Input:
> [Codex / Claude Skills And Context Governance Research](../../reference/codex-claude-skill-context-governance.md)
>
> Architecture Inputs:
> [Context Manager](../../architecture/context-manager.md),
> [Architecture Overview](../../architecture/overview.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md)

---

## 1. 目标

本技术方案把 Skill Governance Plan 落到可实现的后端边界。

目标不是实现公共 Skill 平台，而是在 Product 1.1 中建立一个最小、
可追踪、可预算、可权限治理的 skill 接入方式：

```text
SkillDescriptor
  -> SkillRegistry
  -> SkillActivation
  -> SkillContextSource
  -> Context Manager render / trace
  -> Audit / diagnostics metadata
```

核心约束：

- skill 是上下文和工作流，不是 action；
- tool 才是 action；
- skill 不能给自己授予新的权限；
- skill body 只有激活后才能进入上下文；
- 所有激活、加载、截断、权限拒绝都必须可追踪。

## 2. 非目标

- 不实现公共 skill marketplace。
- 不实现用户自定义 skill UI。
- 不实现 MCP skill bundle。
- 不实现 Router / Collaborator 的完整 skill 自动分配。
- 不实现 forked subagent skill execution。
- 不改 Main Page UI。
- 不替换当前 Context Manager。
- 不把 Codex 开发用 `.agents/skills` 直接当作 Taskweavn 运行时 skill。

最后一点很重要：仓库里的 `.agents/skills` 是 Codex 开发工作流技能，
不是 Taskweavn 产品运行时技能。Taskweavn Runtime 的 skill roots 必须
由产品配置显式给出，不能默认扫描开发代理的 workflow guard。

## 3. 当前代码接入点

已有可复用基础：

| 文件 | 现状 | 影响 |
|---|---|---|
| `src/taskweavn/context/models.py` | 已有 `SkillSummary`、`ExecutionGuidance.active_skills`。 | 可作为 v0 skill summary 输出。 |
| `src/taskweavn/context/sources.py` | 已有 `GuidanceContextSource`。 | 可以新增 `SkillContextSource`，再与 guidance 合并。 |
| `src/taskweavn/context/manager.py` | `SessionContextManager` 统一收集 task/event/workspace/ask/control/guidance。 | skill 应作为 Context Manager source 接入。 |
| `src/taskweavn/context/renderer.py` | 当前只渲染 active skill 名称。 | 需要扩展为 active skill summary/body/resource refs。 |
| `src/taskweavn/context/models.py` | `ContextTrace` 已有候选和 segment hash，但没有 skill trace 字段。 | 需要扩展 trace 元数据。 |
| `ExecutionControls` | 已有 allowed/denied/requires approval/file scopes。 | 可作为 permission merge 的输出目标。 |

设计原则：

```text
不要新增一条绕过 Context Manager 的 skill prompt 通道。
```

所有 skill 上下文都必须经过 `TaskExecutionContextV0` 或后续版本的结构化
上下文，再由 renderer 输出。

## 4. 模块边界

建议新增后端包：

```text
src/taskweavn/skills/
  __init__.py
  models.py
  registry.py
  activation_store.py
  policy.py
  context_source.py
```

建议测试目录：

```text
tests/unit/skills/
  test_skill_models.py
  test_skill_registry.py
  test_skill_activation_store.py
  test_skill_permission_policy.py
  test_skill_context_source.py

tests/integration/context/
  test_skill_context_manager_integration.py
```

不建议在第一步放入：

- frontend routes；
- broad HTTP API；
- skill authoring UI；
- third-party installation flow。

## 5. Pydantic Model Design

模型应使用与 Context Manager 一致的严格风格：

- `extra="forbid"`；
- immutable / frozen；
- explicit literal status；
- validated non-empty ids；
- JSON-safe fields。

实现时可以复用 `taskweavn.context.models.ContextModel`，或在
`taskweavn.skills.models` 中定义同等约束的 `SkillModel`。

### 5.1 Literal Types

```python
SkillSourceScope = Literal[
    "internal",
    "repo",
    "workspace",
    "user",
    "managed",
]

SkillTrustLevel = Literal[
    "trusted",
    "repo_trusted",
    "user_trusted",
    "untrusted",
]

SkillActivationTrigger = Literal[
    "explicit_user",
    "task_capability_match",
    "router_or_collaborator",
    "policy_required",
    "agent_requested",
]

SkillActivationScope = Literal[
    "task_run",
    "session",
    "workflow",
]

SkillActivationStatus = Literal[
    "candidate",
    "policy_checked",
    "active",
    "blocked",
    "completed",
    "expired",
]

SkillPermissionOutcomeKind = Literal[
    "granted_by_runtime",
    "narrowed_by_skill",
    "approval_required_by_skill",
    "denied_by_runtime",
    "denied_by_skill",
    "blocked_untrusted_skill",
]
```

Product 1.1 v0 只应实际使用：

- source scope: `internal`, `repo`, `workspace`；
- activation scope: `task_run`；
- triggers: `task_capability_match`, `policy_required`, optional
  `agent_requested`。

### 5.2 SkillResourceRef

```python
class SkillResourceRef(SkillModel):
    ref_id: str
    kind: Literal["reference", "script", "asset", "template"]
    path: str
    description: str | None = None
    content_hash: str | None = None
    can_act_as_instruction: bool = False
```

规则：

- reference/template 可以进入上下文，但必须经过预算和 trust policy；
- script source 默认不进入上下文；
- script output 只能以 tool/result summary 进入上下文；
- `can_act_as_instruction` 默认 `False`，只有 trusted skill body/section 可为
  instruction。

### 5.3 SkillToolPolicy

```python
class SkillToolPolicy(SkillModel):
    requested_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    requires_approval: tuple[str, ...] = ()
    file_scopes: tuple[str, ...] = ()
```

这不是权限源。它只是 skill 对工具和审批的要求。最终权限仍由 runtime
policy 决定。

### 5.4 SkillDescriptor

```python
class SkillDescriptor(SkillModel):
    skill_id: str
    name: str
    description: str
    source_scope: SkillSourceScope
    source_ref: str
    root_path: str | None = None
    skill_file_path: str | None = None
    content_hash: str
    enabled: bool = True
    implicit_invocation: bool = True
    trust_level: SkillTrustLevel
    tool_policy: SkillToolPolicy = SkillToolPolicy()
    context_requirements: tuple[str, ...] = ()
    resource_refs: tuple[SkillResourceRef, ...] = ()
    risk_tags: tuple[str, ...] = ()
    output_contract: str | None = None
```

Descriptor 来源：

- internal bundled descriptors；
- explicitly configured repo/workspace skill roots；
- future user/managed roots。

不得默认扫描：

- entire workspace；
- `.agents/skills`；
- arbitrary hidden folders；
- downloaded third-party packages。

### 5.5 SkillRegistrySnapshot

```python
class SkillRegistrySnapshot(SkillModel):
    registry_id: str
    workspace_id: str | None = None
    descriptors: tuple[SkillDescriptor, ...]
    scanned_at: datetime
    warnings: tuple[str, ...] = ()
```

Registry snapshot 是 derived view，可以缓存，但不能成为 skill 文件内容的
唯一真相。

### 5.6 SkillActivation

```python
class SkillActivation(SkillModel):
    activation_id: str
    session_id: str
    task_id: str | None = None
    agent_run_id: str | None = None
    skill_id: str
    content_hash: str
    activated_by: SkillActivationTrigger
    activation_reason: str
    trigger_ref: str | None = None
    scope: SkillActivationScope = "task_run"
    status: SkillActivationStatus = "candidate"
    budget_chars: int = 12_000
    loaded_sections: tuple[str, ...] = ()
    loaded_resource_refs: tuple[str, ...] = ()
    denied_requirements: tuple[str, ...] = ()
    created_at: datetime
    updated_at: datetime
    ended_at: datetime | None = None
```

### 5.7 SkillContextSegment

```python
class SkillContextSegment(SkillModel):
    activation_id: str
    skill_id: str
    name: str
    description: str
    source_ref: str
    content_hash: str
    activation_reason: str
    rendered_summary: str
    rendered_instruction_excerpt: str | None = None
    loaded_resource_refs: tuple[str, ...] = ()
    char_estimate: int = 0
    token_estimate: int = 0
    truncated: bool = False
    truncation_reason: str | None = None
```

v0 可以只把 `rendered_summary` 映射到 `ExecutionGuidance.active_skills`。
但 trace 应保留完整 segment metadata。

### 5.8 SkillPermissionMergeResult

```python
class SkillPermissionOutcome(SkillModel):
    kind: SkillPermissionOutcomeKind
    tool: str | None = None
    reason: str
    skill_id: str


class SkillPermissionMergeResult(SkillModel):
    controls: ExecutionControls
    outcomes: tuple[SkillPermissionOutcome, ...]
```

## 6. SQLite Schema

Product 1.1 v0 使用 workspace-local SQLite，建议路径：

```text
<workspace>/.plato/skill_governance.sqlite
```

如果后续已有统一 runtime DB，可以迁移为同库不同表。v0 先独立建库可以降低
耦合。

### 6.1 Registry Cache

Registry cache 是加速和 diagnostics 用的缓存，不是权威数据源。当前实现采用
configured-root scan 直接生成 `SkillRegistrySnapshot`，registry cache store 暂不
作为 Product 1.1 backend foundation 的完成条件。

```sql
CREATE TABLE IF NOT EXISTS skill_registry_cache (
  skill_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  source_scope TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  root_path TEXT,
  skill_file_path TEXT,
  content_hash TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  implicit_invocation INTEGER NOT NULL,
  trust_level TEXT NOT NULL,
  descriptor_json TEXT NOT NULL,
  scanned_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skill_registry_cache_scope
  ON skill_registry_cache(source_scope);
```

### 6.2 Activation Store

```sql
CREATE TABLE IF NOT EXISTS skill_activations (
  activation_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  task_id TEXT,
  agent_run_id TEXT,
  skill_id TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  activated_by TEXT NOT NULL,
  activation_reason TEXT NOT NULL,
  trigger_ref TEXT,
  scope TEXT NOT NULL,
  status TEXT NOT NULL,
  budget_chars INTEGER NOT NULL,
  loaded_sections_json TEXT NOT NULL,
  loaded_resource_refs_json TEXT NOT NULL,
  denied_requirements_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  ended_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_skill_activations_session
  ON skill_activations(session_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_skill_activations_task
  ON skill_activations(session_id, task_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_skill_activations_run
  ON skill_activations(agent_run_id, status);
```

### 6.3 Permission Outcomes

```sql
CREATE TABLE IF NOT EXISTS skill_permission_outcomes (
  outcome_id TEXT PRIMARY KEY,
  activation_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  tool TEXT,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (activation_id) REFERENCES skill_activations(activation_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_permission_outcomes_activation
  ON skill_permission_outcomes(activation_id);
```

### 6.4 Loaded Resource Trace

```sql
CREATE TABLE IF NOT EXISTS skill_loaded_resources (
  resource_load_id TEXT PRIMARY KEY,
  activation_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  ref_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  content_hash TEXT,
  char_count INTEGER NOT NULL,
  truncated INTEGER NOT NULL,
  loaded_at TEXT NOT NULL,
  FOREIGN KEY (activation_id) REFERENCES skill_activations(activation_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_loaded_resources_activation
  ON skill_loaded_resources(activation_id);
```

## 7. Registry Scanner Algorithm

### 7.1 Inputs

```python
SkillRegistryConfig(
    roots=tuple[SkillRootConfig, ...],
    allow_untrusted=False,
    max_skills=100,
)
```

`SkillRootConfig`:

- `source_scope`;
- `root_path`;
- `trust_level`;
- `enabled`;
- `allow_implicit_invocation_default`。

### 7.2 Scan Steps

1. Resolve each configured root through workspace path policy when workspace
   scoped.
2. Reject missing roots with warning, not fatal error.
3. Find child directories containing `SKILL.md`.
4. Parse frontmatter.
5. Validate required `name` and `description`.
6. Build stable `skill_id`.
7. Hash `SKILL.md` plus supported metadata files.
8. Collect resource refs from known folders:
   - `references/`;
   - `scripts/`;
   - `assets/`;
   - `templates/`.
9. Apply trust policy.
10. Sort descriptors deterministically by `source_scope`, `name`, `source_ref`.
11. Optionally save registry cache snapshot in a later optimization slice.

### 7.3 Frontmatter Parser

v0 should avoid adding a YAML dependency unless the project already has one.

Implement a conservative parser:

- require `---` start/end delimiters;
- support top-level scalar string/bool/list values only;
- require `name` and `description`;
- ignore unsupported nested metadata with warning;
- fail closed for malformed frontmatter.

Future versions can adopt a proper YAML parser if skill metadata grows.

## 8. Activation Policy

### 8.1 Candidate Selection

Candidates can be selected by:

- `task.required_capability`;
- explicit runtime policy;
- future Collaborator/Router output;
- future user-selected skill id。

v0 should avoid LLM-ranked skill selection. Deterministic matching is enough:

```text
task.required_capability
  -> descriptor.context_requirements / risk_tags / name / description
  -> candidate skill ids
```

### 8.2 Policy Check

Policy check inputs:

- `SkillDescriptor`;
- `ContextBuildRequest`;
- current `ExecutionControls`;
- workspace/session trust settings。

Policy check rejects when:

- descriptor disabled;
- trust level untrusted;
- content hash differs from stored activation without reactivation;
- requested tool is denied by runtime and required for skill use;
- required context kind is unavailable and skill cannot degrade gracefully。

Blocked activation should persist with `status="blocked"` and `denied_requirements`.

### 8.3 Activation Persistence

Activation becomes durable before context render:

```text
candidate -> policy_checked -> active -> context render
```

This ensures a failed render or runtime crash can still explain why the skill was
selected.

## 9. SkillContextSource Integration

### 9.1 Interface

```python
class SkillContextSource:
    def collect(
        self,
        request: ContextBuildRequest,
        controls: ExecutionControls,
    ) -> SkillContextSourceResult: ...
```

`SkillContextSourceResult`:

```python
class SkillContextSourceResult(SkillModel):
    guidance: ExecutionGuidance
    segments: tuple[SkillContextSegment, ...] = ()
    permission_merge: SkillPermissionMergeResult | None = None
```

### 9.2 SessionContextManager Change

Current flow:

```text
task/event/workspace/ask/control/guidance
  -> TaskExecutionContextV0
```

Proposed flow:

```text
control_source.collect()
  -> skill_context_source.collect(request, controls)
  -> merge controls with skill permission result
  -> merge guidance with skill guidance
  -> TaskExecutionContextV0
  -> ContextTrace(skill metadata)
```

This keeps skill policy before rendering and keeps final `ExecutionControls`
authoritative.

### 9.3 Guidance Merge

Guidance merge rule:

```text
final_guidance.project_rules =
  base_guidance.project_rules

final_guidance.active_skills =
  base_guidance.active_skills + skill_guidance.active_skills

final_guidance.output_requirements =
  base_guidance.output_requirements + skill_guidance.output_requirements
```

Deduplicate by skill name/source ref while preserving order.

## 10. Renderer Changes

### 10.1 v0 Renderer Output

Renderer should add a dedicated section:

```text
## Active Skills
- name: Precision file editing
  reason: task requires bounded line-range edits
  source_ref: internal://skills/precision-file-editing
  content_hash: ...
  instruction_summary:
    ...
```

If no skill is active:

```text
## Active Skills
- none
```

### 10.2 Body Loading

Full `SKILL.md` body is not mandatory in v0. v0 can start with:

- name;
- description;
- reason;
- selected instruction excerpt;
- output requirements;
- resource refs.

Body/excerpt loading must set:

- `char_estimate`;
- `token_estimate`;
- `truncated`;
- `truncation_reason`。

### 10.3 Cache-Aware Rendering

When `render_mode="start_context"`:

- active skill summaries may belong in stable prefix;
- active skill body can be stable only if activation and hash are stable.

When `render_mode="delta_context"`:

- add skill context only if a skill was newly activated, changed, blocked, or
  policy requires reattachment.

When `render_mode="checkpoint_context"`:

- include active skill summaries and any critical instruction excerpt.

## 11. Budget Policy

Add a `SkillContextBudget` or extend `ContextBudget`.

```python
class SkillContextBudget(SkillModel):
    max_skill_index_chars: int = 8_000
    max_active_skill_summary_chars: int = 2_000
    max_active_skill_body_chars: int = 12_000
    max_skill_resource_chars: int = 16_000
```

Implementation option:

- keep as separate config in `SkillContextSource` for SG-3；
- later fold into `ContextBudget` when broader context policy is redesigned。

Trim order:

1. omit inactive low-priority descriptors;
2. shorten descriptions;
3. keep active skill names/reasons/hashes;
4. trim active body excerpts;
5. replace resource excerpt with source ref；
6. record truncation in trace。

## 12. Permission Merge

### 12.1 Function

```python
def merge_skill_controls(
    *,
    base: ExecutionControls,
    descriptor: SkillDescriptor,
) -> SkillPermissionMergeResult:
    ...
```

### 12.2 Rules

1. `base.denied_tools` always wins.
2. `descriptor.tool_policy.denied_tools` narrows effective allowed tools.
3. `descriptor.tool_policy.requested_tools` cannot add tools absent from
   `base.allowed_tools`.
4. `requires_approval` is unioned and deduplicated.
5. `file_scopes` are intersected where both sides specify scopes.
6. Untrusted skill produces `blocked_untrusted_skill`.
7. Outcome rows are recorded for every requested, denied, or approval-gated
   tool.

### 12.3 Example

```text
base.allowed_tools = ("read_file_range", "replace_file_range")
base.denied_tools = ("shell",)

skill.requested_tools = ("replace_file_range", "shell")
skill.requires_approval = ("replace_file_range",)

effective.allowed_tools = ("read_file_range", "replace_file_range")
effective.denied_tools = ("shell",)
effective.requires_approval = ("replace_file_range",)

outcomes:
- replace_file_range: granted_by_runtime + approval_required_by_skill
- shell: denied_by_runtime
```

## 13. Trace Schema Changes

Extend `ContextTrace` with:

```python
class ContextTrace(ContextModel):
    ...
    active_skill_ids: tuple[str, ...] = ()
    active_skill_hashes: tuple[str, ...] = ()
    skill_activation_ids: tuple[str, ...] = ()
    skill_context_segment_hashes: tuple[str, ...] = ()
    skill_permission_outcomes: tuple[SkillPermissionOutcome, ...] = ()
    skill_truncation_count: int = 0
```

If direct model import creates circular dependencies, use a lightweight
`ContextSkillTrace` model in `context.models` and map from `skills.models`.

### 13.1 Snapshot Storage

`ContextSnapshot.task_execution_context.guidance.active_skills` remains the
human-readable active skill summary.

`ContextTrace` owns activation/hash/truncation/permission metadata.

This split prevents bloating every task execution snapshot with detailed skill
resource payloads.

## 14. Resource Loading Policy

Skill resources should use refs first.

Rules:

1. Load no resource by default.
2. Load reference excerpts only when activation or skill body says they are
   required.
3. Never load script source into prompt by default.
4. Any loaded excerpt must include `content_hash`, char count, and truncation.
5. Resource path must resolve under the skill root.
6. Symlink escapes are rejected.
7. External network resources are unsupported in v0.

## 15. Error Model

Define skill-specific errors:

| Code | Meaning | Retryable |
|---|---|---|
| `skill_descriptor_invalid` | `SKILL.md` metadata invalid. | false |
| `skill_disabled` | Skill exists but disabled. | false |
| `skill_untrusted` | Skill not trusted for activation. | false |
| `skill_hash_changed` | Stored activation hash differs from current descriptor. | true after reactivation |
| `skill_required_tool_denied` | Skill requires tool denied by runtime. | false until config changes |
| `skill_resource_unavailable` | Referenced file missing or unreadable. | true if file restored |
| `skill_context_budget_exceeded` | Skill context truncated. | true with larger budget |

These errors should appear in diagnostics and trace. Product UI can initially
show only generic capability unavailable labels.

## 16. First Internal Skill Proof

Recommended first proof:

```text
internal://skills/precision-file-editing
```

Reason:

- Product 1.1 already has Precision File Tools.
- Skill can improve Agent behavior by preferring line-range read/search/replace.
- Permission boundary is clear: the skill requests existing precision tools,
  but cannot grant them.
- Trace can prove the skill influenced context without adding broad UI.

Descriptor:

```text
name: precision-file-editing
description: Use when executing coding tasks that should prefer bounded
line-range read, search, replace, and append operations over full-file writes.
```

Tool policy:

```text
requested_tools:
  - read_file_range
  - search_workspace
  - replace_file_range
  - append_file
requires_approval:
  - replace_file_range
  - append_file
```

## 17. Implementation Slices

### SG-TD-0. Technical Design

Status: implemented.

Acceptance:

- models, schema, scanner, context source, budget, permission merge, trace, and
  test plan are defined.

### SG-TD-1. Models And Registry Scanner

Status: implemented.

Files:

- `src/taskweavn/skills/models.py`
- `src/taskweavn/skills/registry.py`
- `tests/unit/skills/test_skill_models.py`
- `tests/unit/skills/test_skill_registry.py`

Acceptance:

- descriptors validate strictly;
- scanner ignores non-configured roots;
- hash and ordering are deterministic.

### SG-TD-2. Activation Store

Status: implemented.

Files:

- `src/taskweavn/skills/activation_store.py`
- `tests/unit/skills/test_skill_activation_store.py`

Acceptance:

- activation records persist and query by session/task/run;
- blocked/completed/expired states round-trip;
- restart recovery test passes.

### SG-TD-3. Permission Merge

Status: implemented.

Files:

- `src/taskweavn/skills/policy.py`
- `tests/unit/skills/test_skill_permission_policy.py`

Acceptance:

- deny wins;
- skill cannot grant unavailable tools;
- approval requirements are preserved;
- merge outcomes are recorded.

### SG-TD-4. SkillContextSource

Status: implemented.

Files:

- `src/taskweavn/skills/context_source.py`
- `src/taskweavn/context/manager.py`
- `src/taskweavn/context/renderer.py`
- `tests/unit/skills/test_skill_context_source.py`
- `tests/integration/context/test_skill_context_manager_integration.py`

Acceptance:

- active skill summary reaches `ExecutionGuidance.active_skills`;
- skill body/excerpt loads only after activation;
- budget truncation is deterministic;
- task identity and controls survive tight budgets.

### SG-TD-5. Trace And Diagnostics

Status: implemented for ContextTrace metadata and diagnostics-safe summary
projection. Broader Audit/UI projection remains deferred.

Files:

- `src/taskweavn/context/models.py`
- `src/taskweavn/context/store.py`
- diagnostics projection files, if needed.

Acceptance:

- trace includes skill ids, hashes, activation ids, segment hashes, permission
  outcomes, and truncation count;
- diagnostic bundle can expose skill activation metadata without raw prompt
  payloads.

### SG-TD-6. Internal Skill Proof

Status: implemented with `internal:precision-file-editing`.

Files:

- internal skill descriptor/source root;
- integration test with precision file tools or a fake tool profile.

Acceptance:

- a task capability activates the internal skill;
- permission merge blocks unavailable requested tools;
- Agent context includes active skill summary and trace metadata.

### SG-TD Implementation Evidence

Implemented files:

- `src/taskweavn/skills/models.py`
- `src/taskweavn/skills/registry.py`
- `src/taskweavn/skills/activation_store.py`
- `src/taskweavn/skills/policy.py`
- `src/taskweavn/skills/context_source.py`
- `src/taskweavn/skills/__init__.py`
- `src/taskweavn/diagnostics/skills.py`
- `src/taskweavn/context/models.py`
- `src/taskweavn/context/manager.py`
- `src/taskweavn/context/renderer.py`
- `src/taskweavn/diagnostics/bundle.py`
- `tests/test_skill_governance.py`

Verified on 2026-06-11:

- `uv run pytest tests/test_skill_governance.py tests/test_context_manager.py`
- `uv run ruff check src/taskweavn/skills src/taskweavn/context tests/test_skill_governance.py`
- `uv run mypy src/taskweavn/skills src/taskweavn/context`

## 18. Test Matrix

| Area | Test |
|---|---|
| Descriptor | missing `name`, missing `description`, invalid scope, disabled skill. |
| Scanner | configured root only, deterministic order, hash changes, resource refs. |
| Registry cache | deferred optimization: save/load cache and stale hash warning. |
| Activation | create active, block, complete, expire, query by session/task/run. |
| Restart | persisted activation survives new store instance. |
| Context source | metadata-only before activation, active skill after activation. |
| Budget | body/resource truncation recorded, task identity retained. |
| Permission | deny wins, requested unavailable tool denied, approval unioned. |
| Trace | ids/hashes/reason/resource refs/outcomes stored. |
| Internal proof | precision-file-editing activates and renders predictably. |

## 19. Open Decisions Before Code

1. Is `skill_governance.sqlite` acceptable as a separate store, or should skill
   tables live in an existing workspace runtime database?
2. Should v0 parse only `SKILL.md` frontmatter, or also support Codex-style
   `agents/openai.yaml` metadata?
3. Should `SkillContextSegment` be stored directly in `ContextTrace`, or only
   referenced by segment hashes?
4. Should skill activation be persisted at `candidate` time or only after
   policy check?
5. Is the first internal proof `precision-file-editing`, or should it be a
   read-only workspace inspection skill?

## 20. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Implement Skill Governance diagnostics projection.

Scope:
- Project ContextTrace skill metadata into diagnostics-safe summaries.
- Expose active skill id/hash/reason/outcomes without raw prompt payloads.
- Add tests that diagnostics include skill activation metadata and permission
  outcomes.

Do not:
- Add frontend UI.
- Add public skill marketplace or user-authored skill install flow.
- Scan .agents/skills by default.
- Execute skill scripts directly.
```
