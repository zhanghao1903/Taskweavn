# Product 1.1 Skill Governance Plan

> Status: implemented backend governance foundation on branch
>
> Last Updated: 2026-06-11
>
> Product Baseline:
> [Plato Product 1.1 Plan](../../product/plato-1-1-product-plan.md)
>
> Focus Memo:
> [Workspace-Aware Agent Foundation](../../product/plato-1-1-workspace-aware-agent-foundation.md)
>
> Research Input:
> [Codex / Claude Skills And Context Governance Research](../../reference/codex-claude-skill-context-governance.md)
>
> Technical Design:
> [Product 1.1 Skill Governance Technical Design](product-1-1-skill-governance-technical-design.zh-CN.md)
>
> Architecture Inputs:
> [Context Manager](../../architecture/context-manager.md),
> [Architecture Overview](../../architecture/overview.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md)

---

## 1. Purpose

Product 1.1 needs skill support, but the first problem is governance, not a
public skill marketplace.

Skills primarily affect context. A skill tells an Agent how to approach a task,
what references matter, what output shape is expected, and which tools may be
needed. If Taskweavn treats skills as unbounded prompt text, they will pollute
execution context, weaken permission boundaries, and make Agent behavior hard
to debug.

This plan defines the first Product 1.1 Skill Governance slice:

```text
SkillRegistry
  -> SkillActivation
  -> SkillContextSource
  -> budget policy
  -> permission merge
  -> context trace / audit visibility
```

The goal is to make skills safe, traceable, and context-aware before they are
used for broad routing, custom Agent creation, MCP orchestration, or user-facing
skill authoring.

## 2. Product Decision

Product 1.1 should start with local/project skill governance.

Decision:

```text
Skill is context and workflow.
Tool is action.
Permission policy remains runtime-owned.
```

Product 1.1 should not start with:

- public skill marketplace;
- user-generated skill authoring UI;
- cross-session skill memory;
- skill-driven tool permission escalation;
- MCP skill bundles;
- multi-Agent routing productization.

The first implementation should support a small set of trusted internal or
repo-local skills and make their context effects observable.

## 3. Goals

1. Define a canonical `SkillRegistry` boundary for installed/available skills.
2. Define `SkillActivation` lifecycle and scope.
3. Add a `SkillContextSource` concept that integrates with Context Manager.
4. Keep skill metadata cheap and full skill bodies gated by activation.
5. Add a budget policy so active skills cannot crowd out task identity,
   permissions, recent facts, or user instructions.
6. Merge skill tool requirements with runtime permissions without allowing
   skills to grant themselves new authority.
7. Record skill activation, loaded resources, truncation, and denied tool
   requests in context traces.
8. Reserve Main Page / Audit / diagnostics visibility for active skills.
9. Prove the model with one narrow internal skill before broader skill support.

## 4. Non-Goals

- No full public Agent protocol.
- No public skill marketplace or install flow.
- No skill authoring UI.
- No automatic model-generated skills.
- No semantic skill search or vector ranking.
- No MCP integration through skills.
- No forked subagent skill execution.
- No cross-session skill learning.
- No direct frontend implementation in this plan.

## 5. User-Facing Behavior

Most users should not need to understand skills.

Expected first behavior:

- Taskweavn may automatically activate a trusted internal skill when a Task
  requires a known capability.
- The user may see a lightweight capability label in a task detail or debug
  surface, such as `Skill: Precision file editing`.
- Audit/diagnostics can explain which skill influenced an Agent run.
- A skill cannot silently unlock more tools or broader file access.

Advanced behavior reserved for later:

- explicitly selecting a skill from UI;
- editing skill configuration;
- installing third-party skills;
- showing a full skill marketplace.

## 6. Scope Model

Skill governance has three scopes.

| Scope | Meaning | Product 1.1 v0 Decision |
|---|---|---|
| Registry scope | Where a skill descriptor is discovered. | Support repo/project and internal trusted skills first. |
| Session scope | Which skills are available or recently active in a Session. | Keep compact availability and activation summaries. |
| Task-run scope | Which skills actively affect one Agent run. | Primary v0 activation scope. |

Product 1.1 v0 should not use cross-session skill memory. If a skill is useful
again in a later Session, it should be reactivated from registry facts.

## 7. SkillRegistry

`SkillRegistry` owns installed/available skill descriptors. It does not decide
execution state and does not mutate workspace files.

### 7.1 Descriptor Shape

Proposed descriptor fields:

| Field | Purpose |
|---|---|
| `skill_id` | Stable id, preferably scoped, such as `repo:precision-file-editing`. |
| `name` | Human and model-readable skill name. |
| `description` | Activation metadata. This must be concise and trigger-oriented. |
| `source_scope` | `internal`, `repo`, `workspace`, `user`, or future `managed`. |
| `source_ref` | Safe path/package reference for trace and debug. |
| `root_path` | Local root path when filesystem-backed. |
| `content_hash` | Hash of `SKILL.md` and relevant metadata at scan time. |
| `enabled` | Whether the skill may be considered for activation. |
| `implicit_invocation` | Whether automatic activation is allowed. |
| `trust_level` | `trusted`, `repo_trusted`, `user_trusted`, or `untrusted`. |
| `tool_requirements` | Tool names requested by the skill. |
| `tool_denials` | Tools the skill explicitly avoids. |
| `approval_requirements` | Tool/action classes requiring approval. |
| `context_requirements` | Required context kinds, such as files, diffs, task facts, or audit facts. |
| `resource_refs` | Referenced docs/assets/scripts, represented as refs, not loaded content. |
| `risk_tags` | File write, external network, shell, secrets, destructive action, etc. |
| `output_contract` | Optional expected output shape or result format. |

### 7.2 Registry Rules

1. Registry reads descriptors, validates them, and exposes a compact index.
2. Registry does not load every full `SKILL.md` body into execution context.
3. Duplicate names are allowed only if scoped ids remain unique.
4. Disabled or invalid skills must not be activated.
5. Untrusted skills may be visible only as unavailable candidates until a trust
   decision exists.
6. Hash changes must be visible in trace/debug output.

## 8. SkillActivation

`SkillActivation` records that a skill is allowed to affect a specific context
build or Agent run.

### 8.1 Activation Triggers

Supported triggers for Product 1.1 v0:

| Trigger | Meaning | Default |
|---|---|---|
| `explicit_user` | User requested a skill/capability. | Allowed later, not required for v0 UI. |
| `task_capability_match` | Task required capability matches descriptor metadata. | Allowed. |
| `router_or_collaborator` | Future Collaborator/Router selected the skill. | Reserved. |
| `policy_required` | Product workflow requires a skill/gate. | Allowed for internal skills. |
| `agent_requested` | Agent asked to load a skill during execution. | Allowed only through policy checks. |

### 8.2 Activation Record Shape

Proposed activation fields:

| Field | Purpose |
|---|---|
| `activation_id` | Stable activation id. |
| `session_id` | Session boundary. |
| `task_id` | Task boundary when applicable. |
| `agent_run_id` | Agent run that consumed the activation. |
| `skill_id` | Activated skill descriptor id. |
| `content_hash` | Descriptor/body hash at activation time. |
| `activated_by` | Trigger source. |
| `activation_reason` | Short human/debug-readable reason. |
| `trigger_ref` | User message, task, command, or policy ref. |
| `scope` | `task_run` first; future `session` or `workflow`. |
| `status` | `active`, `blocked`, `expired`, or `completed`. |
| `budget` | Context budget assigned to this skill. |
| `loaded_sections` | Skill body sections loaded into context. |
| `loaded_resource_refs` | References expanded for this activation. |
| `denied_requirements` | Tool/resource requirements denied by policy. |
| `started_at` / `ended_at` | Lifecycle timestamps. |

### 8.3 Lifecycle

```text
candidate
  -> policy_checked
  -> active
  -> completed / expired

candidate
  -> blocked
```

Rules:

1. Activation must be policy-checked before context rendering.
2. A blocked activation should be traceable and optionally user-visible in
   diagnostics.
3. Task-run activations expire when the Agent run ends.
4. Session summaries may retain "recently active" skill facts for audit/debug.
5. Reactivation after restart should use persisted activation records plus
   current skill hash validation.

## 9. SkillContextSource

`SkillContextSource` is the Context Manager adapter that turns skill registry
and activation facts into structured execution context.

### 9.1 Inputs

Inputs:

- current `ContextBuildRequest`;
- `SkillRegistry` compact index;
- active `SkillActivation` records for session/task/agent run;
- runtime permission policy;
- context budget policy;
- optional resource loader for selected references.

### 9.2 Outputs

For Product 1.1 v0, output should extend `ExecutionGuidance` rather than
replacing Context Manager:

```text
ExecutionGuidance
  project_rules
  active_skills
  output_requirements
```

The existing `SkillSummary` can carry:

- `name`;
- `description`;
- `source_ref`.

Likely follow-up model:

```text
SkillContextSegment
  skill_id
  content_hash
  activation_reason
  loaded_summary
  loaded_instruction_excerpt
  loaded_resource_refs
  token_or_char_estimate
  truncated
```

### 9.3 Rendering Rules

1. Available skill index is rendered as compact metadata only.
2. Active skill summary is rendered before full skill body.
3. Full skill body or selected sections are rendered only when active.
4. Resource files are rendered only by ref or bounded excerpt.
5. Script source is not rendered by default.
6. Script output enters context as tool/result summary if executed.
7. Skill context must not obscure task identity, user instruction, permissions,
   ASK facts, interruption facts, or recent failure facts.

## 10. Budget Policy

Taskweavn currently uses deterministic Context Manager budgets. Skill support
should extend that policy instead of creating a separate prompt path.

### 10.1 Priority Order

Context rendering priority:

1. system/developer/product rules;
2. task identity and current objective;
3. execution controls and permission boundaries;
4. latest user instruction / ASK / confirmation facts;
5. active skill summaries;
6. selected active skill instructions;
7. recent task events and tool observations;
8. selected file/workspace snippets;
9. skill resource excerpts;
10. low-priority historical context.

This order means skill content is important, but it must not crowd out the
facts required for safe execution.

### 10.2 Proposed v0 Limits

These are starting limits for technical design, not final API constants:

| Segment | Default | Behavior When Exceeded |
|---|---:|---|
| Available skill index | 8,000 chars or 2% of context budget | shorten descriptions, then omit low-priority skills. |
| Active skill summaries | 2,000 chars | keep ids/reasons, trim descriptions. |
| Active skill body | 12,000 chars per run | include selected sections, mark `truncated=true`. |
| Skill resource excerpts | 16,000 chars total | include refs and summaries instead of full text. |
| Script/tool output | existing tool result limits | summarize and store raw ref when needed. |

### 10.3 Budget Trace

Every context trace should record:

- selected skills;
- omitted skills count;
- active body chars/tokens;
- resource excerpt chars/tokens;
- truncation reason;
- whether a critical skill was reattached by policy.

## 11. Permission Merge Policy

Skill requirements can narrow or request permissions. They cannot grant new
authority.

### 11.1 Effective Permission Rule

```text
effective permission =
  baseline runtime policy
  intersected with workspace/session/task policy
  narrowed by skill denials
  annotated by skill requested tools
  gated by approval policy
```

Rules:

1. Deny wins.
2. Runtime baseline wins over skill requirements.
3. A skill may request tools, but unavailable tools stay unavailable.
4. A skill may require stricter approval than runtime default.
5. A skill may not disable required product safety checks.
6. Skill scripts execute only through approved tool/script adapters.
7. File scope restrictions apply to skill references and scripts.
8. Permission merge results must be traceable.

### 11.2 Permission Outcomes

| Outcome | Meaning |
|---|---|
| `granted_by_runtime` | Tool was already allowed and compatible with skill. |
| `narrowed_by_skill` | Skill reduced the effective allowed set. |
| `approval_required_by_skill` | Skill requested additional approval. |
| `denied_by_runtime` | Skill requested a tool not allowed by runtime. |
| `denied_by_skill` | Skill itself forbids a tool/action. |
| `blocked_untrusted_skill` | Skill cannot execute due to trust status. |

## 12. Trace And Audit Model

Skill usage should be explainable after the fact.

### 12.1 Context Trace Fields

Extend context traces with:

- active skill ids;
- skill names and source refs;
- content hashes;
- activation ids and reasons;
- loaded instruction section ids or headings;
- loaded resource refs;
- script/tool output refs;
- budget/truncation info;
- permission merge outcomes;
- blocked activation reasons.

### 12.2 Audit / Diagnostics

Audit and diagnostics should be able to answer:

1. Which skill influenced this Agent run?
2. Why was it selected?
3. Which version/hash was used?
4. Which references were loaded?
5. Did it request tools that were denied or approval-gated?
6. Did skill context get truncated?

Product 1.1 v0 can expose this as debug/diagnostic metadata before building a
full user-facing Skill Inspector.

## 13. Data Ownership

| Object | Owner | Persistence |
|---|---|---|
| `SkillDescriptor` | SkillRegistry | derived from filesystem/package scan; cached by hash. |
| `SkillActivation` | Skill activation store | durable per session/task/agent run. |
| `SkillContextSegment` | Context Manager | stored in context snapshot/trace. |
| Loaded resource excerpt | Context Manager / evidence store | bounded excerpt with source ref/hash. |
| Script execution output | Tool result / observation store | same as other tool outputs. |
| Effective permission result | Permission/runtime policy | trace summary, not a separate authority. |

## 14. Implementation Slices

### SG-0. Plan And Contract

Status: implemented.

Deliver:

- this feature plan;
- optional technical design before implementation;
- gap registry and plan index updates.

Acceptance:

- SkillRegistry, SkillActivation, SkillContextSource, budget, permission merge,
  and trace model are defined enough for implementation planning.

### SG-1. Skill Descriptor And Registry

Status: implemented.

Deliver:

- immutable descriptor model;
- filesystem scanner for trusted internal/repo skill roots;
- descriptor validation and content hashing;
- duplicate/disabled/invalid handling;
- read-only registry query API for backend internals.

Acceptance:

- invalid descriptors are rejected with structured errors;
- duplicate names with unique scoped ids are handled deterministically;
- hashes change when skill content changes;
- no full skill body is loaded into execution context by default.

### SG-2. Skill Activation Store

Status: implemented.

Deliver:

- activation model and SQLite store;
- task-run scoped activation API;
- activation policy check result;
- restart recovery for active/completed/blocked activation records.

Acceptance:

- activation persists across restart;
- activation records include skill hash and reason;
- blocked activation is visible in diagnostics or trace.

### SG-3. SkillContextSource

Status: implemented.

Deliver:

- Context Manager source adapter;
- active skill summary rendering;
- selected body/section loading;
- budget enforcement and truncation metadata.

Acceptance:

- `ExecutionGuidance.active_skills` is populated from activation records;
- active skill body is loaded only after activation;
- task identity and controls remain present even under tight budgets.

### SG-4. Permission Merge

Status: implemented.

Deliver:

- merge function for runtime controls and skill tool requirements;
- denial/approval outcome model;
- tests for deny-wins, approval-required, unavailable tool, and untrusted skill.

Acceptance:

- skills cannot grant a tool not allowed by runtime;
- skill scripts cannot bypass workspace/file policy;
- merge outcome is traceable.

### SG-5. Trace / Audit / Diagnostics

Status: partially implemented. Context trace metadata is implemented; UI/Audit
projection remains deferred.

Deliver:

- context trace extension;
- diagnostic summary fields;
- Audit evidence placeholder/ref for skill activation where useful.

Acceptance:

- a completed task can be traced to active skill id/hash/reason;
- truncated skill context is explicitly reported;
- denied skill requirements appear in diagnostic output.

### SG-6. Internal Skill Proof

Status: implemented for `precision-file-editing`.

Deliver:

- one narrow internal skill, likely for precision file editing or workspace
  inspection;
- activation by task capability match or policy;
- context and trace coverage.

Acceptance:

- the skill improves Agent context without changing runtime permission authority;
- user-visible behavior remains understandable without learning the skill model.

### SG-7. UI / Debug Exposure

Status: deferred.

Deliver:

- optional Main Page detail label for active skill/capability;
- Audit/diagnostic visibility for active skill facts;
- no broad skill management UI.

Acceptance:

- advanced users can inspect active skill facts;
- ordinary users are not forced to select or configure skills.

## 15. Testing Strategy

Current backend foundation evidence:

- `tests/test_skill_governance.py` covers configured-root registry scanning,
  SQLite activation restart recovery, permission merge, Context Manager skill
  activation, trace metadata, and blocked activation.
- `tests/test_context_manager.py` continues to cover existing Context Manager
  behavior after skill integration.
- Targeted checks run on 2026-06-11:
  `uv run pytest tests/test_skill_governance.py tests/test_context_manager.py`,
  `uv run ruff check src/taskweavn/skills src/taskweavn/context tests/test_skill_governance.py`,
  and `uv run mypy src/taskweavn/skills src/taskweavn/context`.

Minimum tests:

- descriptor validation: missing name/description, invalid path, disabled skill;
- registry determinism: ordering, duplicate names, hash stability;
- activation lifecycle: active, blocked, completed, restart recovery;
- context rendering: metadata only before activation, body after activation;
- budget: active skill truncation does not remove task identity or permissions;
- permission merge: runtime deny wins, approval requirement preserved;
- trace: active skill id/hash/reason/resource refs recorded;
- internal proof skill: activation and trace through one AgentLoop/context build.

## 16. Risks

| Risk | Mitigation |
|---|---|
| Skills become hidden prompt magic. | Expose activation and hash in trace/debug. |
| Skills crowd out task facts. | Dedicated budget and priority rules. |
| Skills silently expand tool authority. | Runtime policy remains authoritative; deny wins. |
| Too many skills degrade activation quality. | Compact registry, disabled skills, future ranking. |
| Skill references become prompt injection vectors. | Trust levels and instruction/data separation. |
| Skill body changes make runs unreproducible. | Content hash stored on activation and trace. |
| User-facing skill model increases cognitive load. | Keep v0 mostly automatic and inspectable only. |

## 17. Open Questions

1. Should Product 1.1 v0 allow explicit user skill selection, or only automatic
   internal activation?
2. Should activation be Task-run scoped only, or can a skill become
   Session-sticky?
3. Should skill descriptors live in the same CapabilityCatalog as tools and
   Agents, or remain a separate registry linked by capability ids?
4. How should Collaborator/Router later decide between Workflow, Skill, Agent,
   and Tool?
5. Should a skill's `description` be localized for UI while keeping an
   English/internal activation description?
6. Should skill resource excerpts become durable evidence refs or be reloaded
   by hash on retry?

## 18. Recommended Next Task

Create the Product 1.1 Skill Governance Technical Design:

- concrete Pydantic models;
- SQLite schema for activation records;
- registry scanner algorithm;
- `SkillContextSource` interface;
- budget constants and truncation behavior;
- permission merge function;
- trace schema changes;
- focused test plan.

Do not implement broad skill UI or marketplace behavior before this technical
design is accepted.
