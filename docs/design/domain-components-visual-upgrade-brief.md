# Domain Components Visual Upgrade Brief

> Status: accepted for P4 domain component skeleton and semantic coverage
> Last Updated: 2026-05-26
> Scope: Upgrade targets for canonical Figma page `05 - Domain Components`.
> Non-goals: no Main/Audit screen recomposition, no prototype interactions, no
> frontend code, no old Figma frame migration.

Acceptance note: `05 - Domain Components` passed P4 acceptance on 2026-05-26
for domain component skeleton and semantic coverage. Acceptance covers
structural verification, component existence verification, domain state
coverage, no major overlap, base component reuse, representative domain
content, confirmation lifecycle coverage, and file change/evidence/permission
/risk coverage. It does not cover final visual polish, production copy,
frontend implementation readiness, visual regression baseline, or full dev
handoff readiness.

## 1. Purpose

The canonical `05 - Domain Components` page is structurally valid but still
placeholder-heavy. This brief defines the exact product-density, semantic,
visual, token, state, and verification targets for upgrading domain component
drafts before Main/Audit screen states are recomposed.

Source audit:

- `docs/design/visual-baseline-alignment.md`

Primary source docs:

- `docs/design/design-system.md`
- `docs/design/component-spec.md`
- `docs/design/component-state-matrix.md`
- `docs/design/figma-component-mapping.md`
- `docs/design/figma-readiness-checklist.md`
- `docs/design/layout-components-visual-upgrade-brief.md`
- `docs/product/plato-figma-ui-baseline.md`
- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/canonical-status-model.md`
- `docs/engineering/audit-page-contract.md`
- `docs/ux/screen-state-spec.md`

Figma target:

- canonical file: `Plato Product Design System and Prototype`
- target page: `05 - Domain Components`
- old Figma files: archive/reference only

## 2. Operating Rules

The next Figma task may improve existing domain component sets but must preserve
governance boundaries:

- do not copy historical frames into the canonical file;
- extract patterns, density, and semantic examples only;
- preserve existing component names and node IDs where possible;
- do not create Main Page or Audit Page screen states;
- do not create prototype interactions;
- do not invent new canonical status names or backend fields;
- do not use `Base/Drawer`; drawer behavior remains deferred;
- use canonical tokens and existing Base/Layout components where useful;
- replace generic labels such as `Neutral`, `Primary`, `Card title`, and
  repeated skeleton copy with product-real sample content;
- keep domain notes adjacent to each component set and update readiness status
  to `visual baseline aligned draft`, not `frontend implemented`;
- run descendant-level overlap, clipping, component-set-bound, note/gallery,
  and screenshot-width verification before marking the Figma pass complete.

## 3. Shared Product Content

Use product-real sample content to make density, hierarchy, and wrapping
reviewable. This is example content, not final runtime copy.

Project context:

| Field | Example |
|---|---|
| Project | `Personal Website` |
| Workflow | `Task Planning & Execution` |
| Session | `个人网站项目规划` |
| Task group | `开发实现` |
| Selected task | `实现首页` |

Task tree sample:

```text
个人网站项目规划
├─ 需求分析
│  ├─ 明确目标用户
│  └─ 梳理内容范围
├─ 信息架构
│  ├─ 设计页面结构
│  └─ 定义导航
├─ 视觉方向
├─ 开发实现
│  ├─ 初始化项目
│  └─ 实现首页
└─ 验收与发布
```

Message samples:

- `正在理解目标并整理任务结构。`
- `已生成 Draft TaskTree，等待你审阅。`
- `正在执行：实现首页。`
- `需要确认文件创建动作。`
- `任务完成，已生成结果和文件变更摘要。`

File/audit samples:

| File | Change | Summary |
|---|---|---|
| `src/pages/Home.tsx` | added | `实现首页结构和首屏内容` |
| `src/styles/home.css` | modified | `补充首页布局样式` |
| `docs/site-structure.md` | created | `记录页面结构方案` |

Audit examples:

- `Audit passed`
- `Warning: validation evidence incomplete`
- `Hidden evidence: permission limited`
- `Stale snapshot: records changed`

## 4. Shared Visual Target

Domain components should read as reusable product objects inside a `Modern
Classical Workbench`, not generic component proofs.

Visual direction:

- compact but readable density;
- TaskTree remains the primary control object;
- TaskNode cards expose readiness, execution, confirmation, permission, and
  audit signals without collapsing them into one status;
- Message components support process visibility without becoming chat-first;
- Confirmation is visibly attached to a concrete task/action impact;
- File and Audit components are trust/evidence surfaces, not decorative cards;
- status tones use restrained blue/gold/green/red/gray presentation;
- borders are fine, shadows are low-intensity, radius stays at 8px or below.

Do not introduce:

- marketing hero composition;
- decorative Greek motifs;
- heavy glassmorphism;
- neon/cyber AI styling;
- raw backend payloads, raw logs, stack traces, prompts, provider responses, or
  secret-bearing evidence.

## 5. Required Token Usage

| Usage | Token target |
|---|---|
| Component surface | `color/semantic/surface` |
| Quiet nested surface | `color/semantic/surface-muted` |
| Primary text | `color/semantic/text-primary` |
| Secondary text/metadata | `color/semantic/text-secondary` |
| Border/divider | `color/semantic/border` |
| Selected/focus affordance | `color/semantic/focus-ring`, `shadow/focus` |
| Information/running | `color/status/info` or mapped info token |
| Success/passed/done | `color/status/success` |
| Warning/waiting/partial | `color/status/warning` |
| Danger/failed/denied | `color/status/danger` |
| Panel shadow | `shadow/panel` where elevation is functional |
| Radius | `radius/sm`, `radius/md`, `radius/lg`; never above 8px |
| Typography | `type/eyebrow`, `type/heading`, `type/subheading`, `type/body`, `type/muted`, `type/label` |

Status colors are presentation only. Canonical state dimensions remain owned by
ViewModel fields.

## 6. Component Upgrade Targets

### 6.1 `Domain/TaskTree`

Current node:

- Figma name: `Domain/TaskTree`
- Node ID: `58:55`
- Current readiness: visual baseline aligned draft; refined against the S7
  static tree pattern on 2026-05-25
- Target code path: `src/features/task-tree/components/TaskTree.tsx`

Target role:

TaskTree is the central planning/execution object. It must show hierarchy,
selection, readiness, execution rollup, permission limits, and loading/error
states without becoming a decorative list.

Required visual coverage:

- default tree with project-real hierarchy;
- loading skeleton with stable row heights;
- empty state with next action;
- error state using safe summary;
- readonly/permission-limited state;
- selected node state;
- nested hierarchy with visible indentation and connector rhythm.

Acceptance:

- at least one dense hierarchy sample is visible;
- selected node is visually unambiguous;
- status badges do not replace canonical state dimensions;
- no row labels overlap badges or connectors.
- variant content remains contained by the component root; do not reintroduce
  offset root frames inside variants.

### 6.2 `Domain/TaskNode`

Current node:

- Figma name: `Domain/TaskNode`
- Node ID: `58:203`
- Current readiness: skeleton
- Target code path: `src/features/task-tree/components/TaskNode.tsx`

Target role:

TaskNode shows a single task's readiness, execution, confirmation need, audit
signal, permission/action availability, and interaction state.

Required visual coverage:

- status examples: ready, suggested, running, waiting, completed, failed;
- interaction examples: default, hover, focus, selected, editing, disabled,
  permission denied;
- title, parent/path hint, short description, status badges, action affordance,
  and result/audit/file signal where relevant.

Acceptance:

- status and interaction axes are visually separate;
- running/waiting/completed/failed are distinct at a glance;
- selected and editing states do not rely on color alone;
- dense text wraps without changing card height unpredictably.

### 6.3 `Domain/MessageStream`

Current node:

- Figma name: `Domain/MessageStream`
- Node ID: `59:113`
- Current readiness: skeleton
- Target code path: `src/features/session/components/MessageStream.tsx`

Target role:

MessageStream is process visibility for the session. It should support empty,
loading, streaming, error, partial data, and hidden evidence notes while keeping
TaskTree as the primary control object.

Required visual coverage:

- empty stream guidance;
- loading skeleton;
- streaming process narrative;
- error panel;
- partial-data banner;
- hidden-evidence note.

Acceptance:

- messages are compact and scannable;
- streaming state is visible without implying final completion;
- hidden/partial evidence states are visibly different from empty/error.

### 6.4 `Domain/MessageCard`

Current node:

- Figma name: `Domain/MessageCard`
- Node ID: `59:201`
- Current readiness: skeleton
- Target code path: `src/features/session/components/MessageCard.tsx`

Target role:

MessageCard represents a single process/user/result/warning/error message. It
must differentiate message type and display density.

Required visual coverage:

- info;
- user request;
- assistant response;
- result;
- warning;
- error;
- compact and expanded display examples.

Acceptance:

- message type is clear from label/tone/content, not color alone;
- warning/error examples use safe user-readable copy;
- expanded state shows enough detail without raw payload exposure.

### 6.5 `Domain/ConfirmationPanel`

Current node:

- Figma name: `Domain/ConfirmationPanel`
- Node ID: `60:333`
- Current readiness: skeleton
- Target code path: `src/features/confirmation/components/ConfirmationPanel.tsx`

Target role:

ConfirmationPanel is the explicit user-control surface for risky or
permission-sensitive actions. It must show task/action context, risk, impact,
allowed decisions, lifecycle, and conflict/stale behavior.

Required visual coverage:

- risk levels: low, medium, high;
- lifecycle states: pending, resolving, confirmed, skipped, rejected, expired,
  stale, permission denied, conflict;
- impact summary with file/action examples;
- confirm/skip/reject actions or disabled equivalents.

Acceptance:

- risk and lifecycle are visually separate;
- destructive or high-risk action is not hidden in generic copy;
- permission denied/conflict/stale states show recovery or fallback behavior.

### 6.6 `Domain/FileChangeTable`

Current node:

- Figma name: `Domain/FileChangeTable`
- Node ID: `61:316`
- Current readiness: skeleton
- Target code path: `src/features/audit/components/FileChangeTable.tsx`

Target role:

FileChangeTable shows implementation evidence: file path, change kind, summary,
risk, visibility, and audit/evidence relationship.

Required visual coverage:

- empty;
- loading;
- partial;
- hidden evidence;
- permission denied;
- added;
- modified;
- deleted;
- risky change.

Acceptance:

- file paths truncate safely;
- change kind and evidence visibility remain distinct;
- hidden evidence is not treated as missing data;
- table density is reviewable without overlapping columns.

### 6.7 `Domain/AuditEntryCard`

Current node:

- Figma name: `Domain/AuditEntryCard`
- Node ID: `61:409`
- Current readiness: skeleton
- Target code path: `src/features/audit/components/AuditEntryCard.tsx`

Target role:

AuditEntryCard is the trust entry point from Main Page and the reusable audit
record summary for Audit Page. It must show verdict, scope, subject, evidence
visibility, permissions, stale state, and detail affordance.

Required visual coverage:

- passed;
- warning;
- failed;
- inconclusive;
- not available;
- expanded;
- hidden evidence;
- permission denied;
- stale snapshot.

Acceptance:

- verdict labels align with `docs/engineering/audit-page-contract.md`;
- hidden/permission/stale states are explicit and visually distinct;
- card remains read-only and routes users to the Audit Page for inspection.

## 7. Verification Requirements

The governed Figma upgrade must pass:

- Figma access/token pre-check;
- node inventory check for all seven domain component sets;
- node ID preservation check for all seven component sets;
- descendant-level overlap and clipping verification;
- component-set bounds contain visible descendants;
- note frames do not overlap component galleries;
- effective page width remains within the 1600px review target;
- export verification for all seven component sets;
- repo docs updated with run marker and readiness status;
- frontend source code remains unchanged.

## 8. Acceptance Criteria

The P4.12 upgrade is complete only when:

- all seven domain component sets are upgraded to `visual baseline aligned
  draft`;
- generic skeleton copy is replaced or clearly marked as non-production;
- canonical state dimensions remain separate;
- audit verdict and evidence visibility use the canonical audit contract;
- permission, hidden evidence, partial, stale, loading, empty, and error states
  remain visible where applicable;
- no old Figma frame is copied into the canonical file;
- no Main/Audit screen state is recomposed in this task;
- no frontend source code is modified.

## 9. Embedded Figma Task Prompt

Use the product-workflow-gate skill first.
Use the plato-figma-governance skill next.

Task:
Run the P4.12 governed visual upgrade for `05 - Domain Components` using
`docs/design/domain-components-visual-upgrade-brief.md`.

Do not create new screen states.
Do not create prototype interactions.
Do not migrate old Figma content.
Do not implement frontend code.

Upgrade existing component sets only:

- `Domain/TaskTree`
- `Domain/TaskNode`
- `Domain/MessageStream`
- `Domain/MessageCard`
- `Domain/ConfirmationPanel`
- `Domain/FileChangeTable`
- `Domain/AuditEntryCard`

Preserve component set node IDs where possible. Use product-real sample content,
canonical tokens, and existing state mappings. After writing, verify no visible
overlap, no text clipping, component-set bounds contain visible descendants,
note frames do not overlap galleries, effective width stays within 1600px, and
exports succeed for all seven component sets.
