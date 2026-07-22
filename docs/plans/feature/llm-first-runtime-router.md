# Feature Plan: LLM-First Skill-Driven Runtime Router

> Status: planned
>
> Last Updated: 2026-06-25
>
> Owner: Product / Runtime Input Router / Skill Governance / Execution Plane
>
> Related:
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Runtime Input Router Technical Design](runtime-input-router-contract-technical-design.md),
> [Agent LLM Config And Router LLM](agent-llm-config-and-router-llm.md),
> [Product 1.1 Skill Governance Plan](product-1-1-skill-governance.md),
> [Skill Governance Technical Design](product-1-1-skill-governance-technical-design.zh-CN.md),
> [UI Natural-Language WeChat Send Task](ui-natural-language-wechat-send-task.md),
> [Technical Design](llm-first-runtime-router-technical-design.zh-CN.md)

---

## 1. Problem

The current Runtime Input Router contains deterministic semantic recognition for
natural-language input:

- stop/retry phrase sets;
- question-like phrase heuristics;
- workspace-change phrase heuristics;
- bounded WeChat send phrase parsing.

This was useful for the first safe vertical slice, but it creates the wrong
product behavior:

1. natural language robustness is limited by hardcoded patterns;
2. app-specific knowledge leaks into Router code;
3. adding new software flows requires Router code edits;
4. users expect the Router to understand common phrasing through LLM semantics;
5. skill governance cannot become the central capability mechanism while Router
   bypasses it with embedded semantic rules.

The WeChat example makes the gap visible:

```text
给微信的文件传输助手发送“你好”
```

The desired behavior is not a hardcoded parser tweak. The Router should use LLM
semantic interpretation, guided by Router skills, to recognize this as a task
creation request. The execution layer should later use WeChat operation skills
to complete the task safely.

## 2. Product Decision

Product 1.1 should move Runtime Input Router from deterministic semantic
matching to LLM-first, skill-driven semantic planning.

Decision:

```text
Natural-language input
  -> Router LLM planner with activated Router skills
  -> structured route proposal
  -> deterministic validation / confirmation / idempotency / dispatch gate
```

Hardcoded natural-language semantic recognition should be removed from Router
production code.

Deterministic code remains responsible for:

- request validation;
- active ASK / confirmation state lookup;
- allowed dispatch target calculation;
- permission and side-effect policy;
- idempotency and replay;
- high-risk confirmation requirements;
- command-backed dispatch;
- result, activity, audit, and evidence projection.

Skills own capability semantics and examples. Code owns safety and state
authority.

## 3. Goals

1. Route all Main Page natural-language input through an LLM Router planner.
2. Move stop/retry/resume/cancel command semantics into Router control skills.
3. Move WeChat send phrase and task-creation guidance into a WeChat Router
   skill.
4. Let Router LLM decide whether the input should become:
   - direct read-only answer;
   - read-only inquiry with file/search/context refs;
   - guidance/context update;
   - ASK answer;
   - confirmation response;
   - product command;
   - new task or plan;
   - clarification;
   - unsupported.
5. Ensure LLM output is only a proposal and cannot directly mutate state or run
   tools.
6. Preserve one-primary-side-effect semantics.
7. Preserve high-risk confirmation for external communication and workspace
   mutation.
8. Add route source and skill activation evidence so users and developers can
   see whether routing was LLM-assisted and which skills were used.

## 4. Non-Goals

- No LLM direct workspace writes.
- No LLM direct computer-use calls.
- No external message send without confirmation.
- No removal of structured UI button command paths.
- No public skill marketplace.
- No user-authored skill UI.
- No broad Agent Manager or multi-Agent routing implementation.
- No remote WeChat / LAN worker routing in this slice.
- No one-off WeChat parser expansion as the main fix.

## 5. Boundary Rule

The Router has two distinct inputs:

| Input class | Routing policy |
|---|---|
| Structured UI action, such as a button payload with concrete command kind | May bypass LLM and call command-backed handlers directly. |
| Free-form natural language from the Main Page input | Must go through Router LLM planner. |

This plan targets free-form natural language. It does not require adding LLM
latency to explicit UI buttons that already carry structured command intent.

## 6. Target Router Model

```text
RuntimeInputRouteRequest
  -> ProtocolPreflight
       - validate request shape
       - load selected scope
       - load active ASK / confirmation facts
       - compute allowed dispatch targets
       - build available Router skill list
  -> RouterSkillActivation
       - router-core
       - router-control-commands
       - router-read-only-inquiry
       - router-task-authoring
       - router-wechat-send, when relevant
  -> LLMRuntimeInputRoutePlanner
       - receives skill summaries and selected bodies
       - returns RuntimeInputRouteProposal JSON only
  -> RouteProposalValidator
       - schema validation
       - allowed dispatch target validation
       - confidence / side-effect validation
       - permission validation
       - high-risk confirmation validation
       - capability/task-type validation
  -> Dispatcher
       - read-only inquiry
       - record guidance
       - resolve ASK
       - resolve confirmation
       - existing command
       - execution handoff / task creation
       - clarification / unsupported
```

## 6.1 Configuration Entry Boundary

Current Product 1.1 settings UI exposes only app-level configuration. It does
not provide separate workspace-level or session-level configuration entry
points yet.

For this migration:

- Router mode and Router LLM profile controls are app/global configuration.
- Settings page changes affect the whole app runtime, not one workspace or one
  session.
- Workspace/session override semantics are not part of this slice.
- The design must not imply that users can tune Router behavior per workspace
  or per session until dedicated entry points exist.

Future workspace/session configuration can reuse the centralized runtime
configuration resolver, but it needs a separate product entry, audit surface,
and effective-config explanation.

## 7. Router Skills

Product runtime skills are not the repo `.agents/skills` used by Codex
development. They must be explicit Taskweavn runtime skills governed by
SkillRegistry and SkillActivation.

Minimum Router skills:

| Skill | Purpose |
|---|---|
| `router-core` | Explains intent categories, one-primary-side-effect rule, and output schema expectations. |
| `router-control-commands` | Defines natural-language control commands such as stop, retry, resume, cancel, pause, and their routing constraints. |
| `router-read-only-inquiry` | Defines when to answer directly, when to use read-only context, and how to request safe refs. |
| `router-task-authoring` | Defines when to create a task, update a plan, or ask clarification before task creation. |
| `router-wechat-send` | Defines WeChat send task semantics, required slots, high-risk policy, and task request draft shape. |

Execution-specific app operation skills are separate:

| Skill | Used by | Purpose |
|---|---|---|
| package `wechat-use` | Execution Agent | Loaded from `wechat-desktop-tool`; explains how to operate WeChat Desktop, not how Router parses user input. |

Router skills help create a structured task. Execution skills help complete the
task.

## 8. WeChat Example

Input:

```text
给微信的文件传输助手发送“你好”
```

Expected Router proposal:

```json
{
  "intent": "execution_request",
  "dispatchTarget": "execution_handoff",
  "sideEffect": "execution_request",
  "confidence": "high",
  "visibleReasoningSummary": "The user wants to create a WeChat send task.",
  "taskRequestDraft": {
    "taskType": "communication.wechat.send_message",
    "input": {
      "contactDisplayName": "文件传输助手",
      "messageText": "你好"
    },
    "policy": {
      "requiredCapability": "communication.wechat_desktop_send",
      "requiresHumanConfirmation": true,
      "riskLevel": "high"
    }
  },
  "activatedSkillIds": [
    "router-core",
    "router-wechat-send"
  ]
}
```

Validation and dispatch:

1. validator confirms `communication.wechat.send_message` is allowed;
2. validator confirms contact/message are present;
3. validator enforces confirmation regardless of user wording;
4. Router creates an Execution Plane task;
5. Execution Plane later invokes WeChat runtime;
6. WeChat runtime uses execution-side WeChat skill and computer-use adapter;
7. send happens only after user confirmation.

## 9. Migration Slices

### RLLM-0. Plan And Technical Design

Status: this document.

Acceptance:

- Product decision is documented.
- Existing deterministic semantic limitations are acknowledged.
- Skill/code responsibility boundary is explicit.
- Implementation slices are defined.

### RLLM-1. Router Skill Contracts

Status: implemented foundation.

Create runtime Router skills and capability manifests.

Acceptance:

- `router-core`, `router-control-commands`, `router-read-only-inquiry`,
  `router-task-authoring`, and `router-wechat-send` exist as runtime skill
  descriptors or fixtures.
- Skills include examples but are not trusted as permission sources.
- Skill activation is traceable.

Implementation evidence:

- Runtime skill artifacts exist under `src/taskweavn/runtime_skills/`.
- `router-core`, `router-control-commands`, `router-read-only-inquiry`,
  `router-task-authoring`, and `router-wechat-send` include `SKILL.md` plus
  `manifest.json`.
- package `wechat-use` is adapted into Plato skill governance and activated by
  the WeChat execution capability; Plato does not maintain a duplicate body.
- `tests/test_runtime_router_skills.py` verifies stable skill ids, manifest
  alignment, and WeChat confirmation/slot constraints.

### RLLM-2. Proposal Schema Extension

Extend `RuntimeInputRouteProposal` to represent command and task drafts without
embedding parser-specific fields in Router code.

Status: implemented foundation in this branch. The proposal model now accepts
optional structured draft fields while preserving old minimal proposal
constructors for compatibility.

Candidate additions:

- `routeSource`;
- `activatedSkillIds`;
- `commandDraft`;
- `taskRequestDraft`;
- `requestedReadOnlyContext`;
- `confirmationResponseDraft`, for active confirmation responses;
- `askAnswerDraft`, for active ASK responses.

Acceptance:

- Invalid or unsupported proposal shapes fail closed.
- Mutating proposals require non-low confidence.
- External communication proposals require confirmation.
- `communication.wechat.send_message` proposals require
  `contactDisplayName`, `messageText`,
  `requiredCapability=communication.wechat_desktop_send`,
  `requiresHumanConfirmation=true`, and `riskLevel=high`.
- `existing_command` proposals require an enabled command draft; the initial
  enabled command draft kinds are `stop_task` and `retry_task`.

### RLLM-3. LLM-First Router Dry Run

Enable Router LLM planner in shadow/dry-run mode while existing deterministic
paths still serve production behavior.

Status: partially implemented foundation in this branch. The planner now
receives built-in Router skill prompt context and writes summary runtime logs
for request/config/skills/proposal/validation/fallback. Runtime router dispatch
now writes final dispatch summary logs for request id, route decision, side
effect, outcome, command/inquiry summary, and confirmation requirement without
recording raw user input. Explicit shadow-mode comparison remains later work.

Acceptance:

- Router logs planner input/output using existing LLM logging.
- Router prompt includes active Router skill ids, content hashes, output
  contracts, and bounded instruction excerpts.
- Activity or diagnostics can show `route_source=llm_shadow`.
- No production side effects depend on shadow proposals.
- Golden examples demonstrate expected proposals.

### RLLM-4. Replace Hardcoded Semantic Recognition

Remove natural-language phrase sets from `DefaultRuntimeInputRouter` production
routing.

Status: implemented in this branch. Planner-driven `existing_command` dispatch
now supports `stop_task` and `retry_task` command drafts. Free-form natural
language is routed only by the Router LLM planner. If the planner returns
`invalid` / `unavailable` or no safe proposal, Router fails closed with a
non-mutating unsupported outcome. It does not fall through to code semantic
recognition for stop/retry-like commands, questions, workspace-change requests,
active ASK answers, confirmation responses, or WeChat send requests.

The code should no longer hardcode:

- stop/retry phrase sets;
- question prefix/substrings;
- workspace-change phrase sets;
- WeChat send phrase parsing.

Acceptance:

- Natural-language stop/retry/resume is routed through LLM proposal plus
  `router-control-commands` skill.
- Active ASK answers and active confirmation responses are routed through LLM
  proposal plus deterministic active-state validation when a planner is
  configured.
- Natural-language question is routed through LLM proposal plus
  `router-read-only-inquiry` skill.
- Natural-language WeChat send is routed through LLM proposal plus
  `router-wechat-send` skill.
- Unit tests prove no command dispatch happens when the LLM proposal is invalid.

### RLLM-5. Read-Only Tool Context Routing

Let Router LLM propose read-only context needs while keeping tool execution in
Read-Only Inquiry services.

Acceptance:

- Router does not read arbitrary files directly.
- Read-only file/search/diff requests are represented as validated refs or
  context requests.
- Read-Only Inquiry remains `sideEffect=no_effect`.

### RLLM-6. Execution Handoff Through Skill-Guided Task Drafts

Let Router LLM create task drafts for capability-backed execution handoff.

Status: started. A validated WeChat `taskRequestDraft` can now be adapted into
the existing confirmation-gated WeChat dispatch path. With an Execution Plane
service available, the Router publishes a `communication.wechat.send_message`
`TaskRequest` from the LLM proposal slots instead of re-parsing the raw user
sentence. When the planner is unavailable or invalid, Router returns a
non-mutating unsupported outcome and does not run a code WeChat parser.

Acceptance:

- WeChat send task draft is built from skill-guided proposal and validator.
- General task/plan creation is supported only through accepted command-backed
  paths.
- High-risk policy remains deterministic.

### RLLM-7. Production Switch And Legacy Removal

Switch natural-language Router mode to LLM-first by default after tests pass.

Status: implemented for Router production paths in this branch. Main Page
runtime wires an `LLMRuntimeInputRoutePlanner`, and `DefaultRuntimeInputRouter`
has no compatibility flag for natural-language semantic fallback. Legacy
phrase/parser code and related tests were removed. Explicit UI modes such as
`mode=ask`, `mode=guide`, and `mode=change` remain as structured product
commands, not semantic fallback.

Acceptance:

- Feature flag or config records the active Router mode.
- Code-based natural-language semantic parser is removed.
- Diagnostics expose route source, active skills, confidence, and validator
  decisions.

## 10. Tests

Required tests:

- LLM planner proposal schema round trip.
- Invalid JSON / malformed proposal fails closed with no side effect.
- Low-confidence mutation fails closed.
- Active ASK answer can be proposed by LLM and validated by backend state.
- Active confirmation yes/no can be proposed by LLM and validated by backend
  state.
- Stop/retry/resume natural language routes through Router control skill.
- `给微信的文件传输助手发送“你好”` produces a WeChat task draft in mocked
  planner tests.
- WeChat task draft without contact/message becomes clarification.
- WeChat task draft without confirmation policy is rejected or corrected by
  validator.
- Read-only inquiry proposals cannot include mutation targets.
- LLM unavailable returns a non-mutating unavailable/clarification outcome.

## 10.1 Router Logging Requirements

Router logging is required for this migration. It must be possible to inspect
why a user input went to a route without reading code or guessing whether LLM
was invoked.

Required log events:

- route request received, with session/workspace/scope ids and redacted input
  summary;
- app/global effective Router config snapshot, including router mode and
  planner timeout;
- activated Router skill ids and content hashes;
- LLM planner input/output metadata through the existing Agent LLM logging
  system;
- proposal validation result;
- validator rejection reason, if invalid;
- final dispatch target and side-effect class;
- created command/task/inquiry ids;
- confirmation requirement for high-risk routes;
- fallback reason when planner is unavailable.

Logging rules:

- Do not log hidden chain-of-thought.
- Do not log secrets or raw workspace file contents.
- Raw user input and LLM payload logging follows the existing logging profile
  and redaction policy.
- Summary logs must be available in normal diagnostics; raw prompt/response
  payloads remain gated by debug/full logging profiles.

## 11. Risks

| Risk | Mitigation |
|---|---|
| LLM planner latency affects Main Page input. | Use small router model/profile, timeout, and unavailable fallback. |
| LLM produces invalid or unsafe proposals. | Strict schema and deterministic validator fail closed. |
| Skills become hidden permission grants. | Skill governance: skill is context only; runtime policy owns authority. |
| Prompt injection through user input or workspace content. | Router planner receives bounded facts and skills; workspace file contents are read only by read-only services with disclosure rules. |
| Regression in stop/retry UX. | Keep explicit UI buttons structured; test natural-language command examples. |
| Cost and log volume increase. | Agent-level Router LLM profile, token usage attribution, summary logging by default. |

## 12. Acceptance Criteria

The migration is accepted when:

1. free-form natural language no longer depends on hardcoded semantic phrase
   sets in Router code;
2. Router LLM planner is the default semantic interpreter;
3. Router skills define command, inquiry, task-authoring, and WeChat task
   semantics;
4. deterministic code validates every proposal before side effects;
5. WeChat send natural language creates a confirmation-gated Execution Plane
   task;
6. Execution Agent uses execution-side WeChat skill to operate WeChat;
7. diagnostics expose route source, activated skills, confidence, and validator
   outcome;
8. Router logs expose effective app/global Router config, activated skills,
   proposal validation, dispatch target, and fallback reason;
9. test coverage proves invalid LLM output cannot mutate state or send messages.

## 13. Current Implementation Status

As of 2026-06-25 in this branch:

- built-in trusted runtime Router skills exist and are loaded into the Router
  planner prompt context;
- `RuntimeInputRouteProposal` supports command, task, ASK answer,
  confirmation response, and read-only context drafts;
- mutating/authorizing proposals fail closed unless active backend state and
  draft shape validate;
- Main Page runtime wires `LLMRuntimeInputRoutePlanner`;
- `DefaultRuntimeInputRouter` no longer exposes code semantic fallback
  configuration;
- planner failure/invalid proposal never falls through to code semantic
  recognition for stop/retry/question/change/WeChat/ASK/confirmation text;
- active ASK and active confirmation paths can be resolved from planner
  proposals, and planner failure no longer silently records arbitrary text as
  an ASK answer;
- WeChat free-form input is routed only through planner-produced task drafts;
  the legacy WeChat natural-language parser and parser-only tests have been
  removed;
- runtime config registry exposes the effective Router behavior keys:
  `runtime_input_router.mode`,
  `runtime_input_router.llm_planner_required`,
  `runtime_input_router.planner_failure_policy`,
  `runtime_input_router.skill_source`, and
  `runtime_input_router.max_skill_instruction_chars`;
- diagnostics bundle export includes redacted runtime Router summary logs for
  proposal and validation events, including route source, activated skills,
  confidence, and validator outcome without raw user input.

Remaining before merge:

- PR review and normal branch CI.

Out of scope for this feature:

- workspace/session-level Router configuration UI;
- general Plan/TaskNode mutation command skills beyond the currently validated
  Runtime Input Router slices;
- exposing raw Router LLM prompts or provider payloads in diagnostics.
