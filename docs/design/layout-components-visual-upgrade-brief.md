# Layout Components Visual Upgrade Brief

> Status: accepted for P4 product-aligned layout reference
> Last Updated: 2026-05-26
> Scope: Upgrade targets for canonical Figma page `04 - Layout Components`.
> Non-goals: no Figma modification, no new screen states, no frontend code, no
> old Figma frame migration.

Acceptance note: `04 - Layout Components` passed P4 acceptance on 2026-05-26
for product-aligned layout reference. Acceptance covers product context in
TopBar, workflow/session SideNav hierarchy, AppShell slot structure,
MainWorkArea/DetailPanel/ContextInputBar layout roles, running/readonly/stale
/error layout states, no major overlap/clipping, and valid component mapping.
It does not cover final high-fidelity polish, production copy, frontend
implementation, responsive/mobile final design, or complete interaction
behavior.

## 1. Purpose

The canonical `04 - Layout Components` page is structurally valid but visually
incomplete. This brief defines the exact visual, semantic, density, token,
responsive, and acceptance targets required before the next governed Figma
write upgrades the layout components.

Source audit:

- `docs/design/visual-baseline-alignment.md`

Primary source docs:

- `docs/design/design-system.md`
- `docs/design/component-spec.md`
- `docs/design/component-state-matrix.md`
- `docs/design/figma-component-mapping.md`
- `docs/design/figma-readiness-checklist.md`
- `docs/product/plato-figma-ui-baseline.md`
- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/canonical-status-model.md`
- `docs/ux/screen-state-spec.md`

Figma target:

- canonical file: `Plato Product Design System and Prototype`
- target page: `04 - Layout Components`
- old Figma files: archive/reference only

## 2. Operating Rules

The next Figma task may improve existing layout components but must preserve
governance boundaries:

- do not copy historical frames into the canonical file;
- extract patterns, density, and semantic examples only;
- preserve existing component names and node IDs where possible;
- do not create new product states outside `component-state-matrix.md`;
- do not use `Base/Drawer`; drawer behavior remains deferred;
- use existing Base Components as instances where applicable;
- use canonical tokens and do not introduce ad hoc colors, radius, shadows, or
  spacing values;
- replace placeholder labels such as `Primary`, `Neutral`, `Default panel`,
  and `Panel container skeleton` with product-real example content;
- keep Figma notes near each component and update readiness status to
  `visual baseline aligned draft`, not `frontend implemented`;
- if any component cannot be upgraded without a missing product decision, mark
  it blocked instead of inventing behavior.

## 3. Shared Visual Target

The layout components should express a `Modern Classical Workbench` rather than
a skeleton gallery.

Visual direction:

- desktop-first workbench reference: 1440 x 1024;
- stable top bar, workflow/session sidebar, main workbench region, detail
  inspector, and context input dock;
- restrained blue/gold/cream/gray palette;
- compact but readable type;
- fine borders and low-intensity shadows;
- radius no greater than 8px for panels/cards;
- TaskTree remains the central control object;
- message stream supports process visibility without becoming the primary
  layout driver;
- audit remains a trust entry from Main Page and a read-only Trust Plane in
  Audit Page contexts.

Do not introduce:

- marketing hero composition;
- neon/cyber AI styling;
- decorative Greek UI elements;
- strong glassmorphism;
- nested page-section cards;
- oversized rounded controls;
- large decorative gradients or bokeh/orb backgrounds.

## 4. Required Token Usage

| Usage | Token target |
|---|---|
| App background | `color/semantic/page-bg` |
| Primary panel surface | `color/semantic/surface` |
| Quiet supporting surface | `color/semantic/surface-muted` |
| Primary text | `color/semantic/text-primary` |
| Secondary text/metadata | `color/semantic/text-secondary` |
| Standard borders/dividers | `color/semantic/border` |
| Focus affordance | `color/semantic/focus-ring`, `shadow/focus` |
| Primary action | `color/semantic/action-primary` |
| Selected/hover surface | `color/primitive/clear-blue` or mapped semantic selected token |
| Running/attention | `color/primitive/wisdom-gold` or status warning token |
| Success/done | `color/status/success` |
| Error/denied/failed | `color/status/danger` |
| Panel shadow | `shadow/panel`, only where elevation is functional |
| Radius | `radius/sm`, `radius/md`, `radius/lg`; never above 8px |
| Spacing | `space/1` through `space/10` |
| Typography | `type/eyebrow`, `type/heading`, `type/subheading`, `type/body`, `type/muted`, `type/label` |

Token discipline:

- status colors are presentation only and must not collapse canonical status
  dimensions;
- component notes must identify any missing semantic token rather than
  hardcoding a new visual value;
- all placeholder-only colors from skeleton work must be replaced with mapped
  tokens or explicitly marked as unresolved.

## 5. Shared Semantic Copy Set

Use product-real sample content so density, wrapping, and hierarchy can be
reviewed. This is example content, not final product copy.

Route context:

| Field | Example |
|---|---|
| Product | `Plato` |
| Project | `Personal Website` |
| Workflow | `Task Planning & Execution` |
| Session | `个人网站项目规划` |
| Status chips | `Planning`, `Draft`, `Running`, `Waiting`, `Done`, `Read-only`, `Stale` |
| Autonomy chip | `Balanced autonomy` |
| Scope hint | `Session workspace: isolated` |

Task examples:

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

Message examples:

- `正在理解目标`
- `正在把目标整理成可执行的任务结构。`
- `已生成任务计划，你可以先审阅再执行。`
- `需要确认文件创建动作。`
- `任务已完成，可以查看结果和文件变更。`

Input placeholders:

- session goal: `描述你想完成的事，例如：帮我规划一个个人网站项目`
- task instruction: `正在补充当前任务：设计页面结构`
- clarification answer: `补充你的选择或约束`
- confirmation response: `说明你是否确认、预览、修改或跳过此动作`

File/audit examples:

| File | Change | Summary |
|---|---|---|
| `docs/site-structure.md` | created | `记录页面结构方案` |
| `docs/content-outline.md` | modified | `增加首页内容大纲` |
| `docs/navigation.md` | created | `定义导航结构` |

Audit entry label:

```text
查看这个任务的执行记录
```

## 6. Component Upgrade Targets

### 6.1 `Layout/AppShell`

Current node:

- Figma name: `Layout/AppShell`
- Node ID: `45:24`
- Current readiness: skeleton
- Target code path: `frontend/src/shared/components/layout/AppShell.tsx`

Target role:

`AppShell` owns the stable workbench frame. It should demonstrate how top bar,
workflow/session navigation, main work area, detail inspector, and context
input dock compose into a coherent product surface.

Desktop target:

| Region | Target |
|---|---|
| Frame | 1440 x 1024 reference composition inside the component example |
| Top bar | 72px visual target; route context always visible |
| Sidebar | 272-288px expanded target |
| Main content | flexible center region; TaskTree-first layout |
| Detail panel | 340-380px target; scrolls independently |
| Context input dock | 96-120px target; visible at bottom |
| Page padding/gutters | 16-24px using spacing tokens |

Required states/variants:

- `main / ready`
- `main / loading`
- `main / stale`
- `main / error`
- `audit / ready` as a note or variant only if the follow-up operation gate
  explicitly allows adding documented variants

Semantic content targets:

- show `Personal Website / Task Planning & Execution / 个人网站项目规划`;
- show the selected workflow and selected session;
- show a central TaskTree region, a right detail region, and bottom input
  dock;
- loading state should use real skeleton placement, not generic stacked
  placeholder panels;
- stale/error states must preserve last-known content and show a recovery
  region.

Token targets:

- app background: `color/semantic/page-bg`;
- panels: `color/semantic/surface`;
- borders: `color/semantic/border`;
- muted region: `color/semantic/surface-muted`;
- shadow only for functional panel separation.

Responsive notes:

- wide/desktop: full workbench;
- tablet: sidebar may collapse first, detail panel stacks below or becomes a
  secondary row; do not use Drawer;
- mobile: single-column stack with TopBar context condensed and input dock
  remaining reachable.

Acceptance:

- first-time reviewer can identify product context, current workflow/session,
  main task area, detail area, and input target without reading notes;
- no region overlaps at 1440px and 1600px screenshot widths;
- component examples do not look like unrelated panels placed together.

### 6.2 `Layout/TopBar`

Current node:

- Figma name: `Layout/TopBar`
- Node ID: `45:52`
- Current readiness: skeleton
- Target code path: `frontend/src/shared/components/layout/TopBar.tsx`

Target role:

`TopBar` is the route/context anchor. It must answer: product, project,
workflow, session, current status, and global actions.

Required structure:

| Zone | Required content |
|---|---|
| Product mark | high-resolution `Plato` mark; no visible asset border |
| Project context | label `Project`, value `Personal Website` |
| Workflow chip | `Task Planning & Execution` |
| Session context | `Session: 个人网站项目规划` |
| Status chips | planning/execution/permission chips as separate presentation badges |
| Global actions | `查看审计`, `设置`; Audit entry is visible but not dominant |

Required states/variants:

- default;
- loading;
- readonly / permission-limited;
- stale;
- audit-return context if allowed by the follow-up Figma operation gate.

Semantic copy:

- default: `Project Personal Website`, `Task Planning & Execution`,
  `Session: 个人网站项目规划`, `Planning`;
- running: `Running`, `Balanced autonomy`;
- readonly: `Read-only`, disabled action reason;
- stale: `Stale snapshot`, `Resync`.

Token targets:

- action buttons use `Base/Button` and `color/semantic/action-primary`;
- badges use `Base/Badge` with status tones;
- context labels use `type/eyebrow` or `type/label`;
- values use `type/body` or `type/subheading`;
- separators use `color/semantic/border`.

Responsive notes:

- desktop: full context visible;
- tablet: keep product mark, project, workflow, status, and overflow secondary
  actions;
- mobile: product mark, current session/status, and action overflow; do not
  let long Chinese session text overlap actions.

Acceptance:

- no `Primary` or `Neutral` placeholder labels remain;
- long session text truncates safely with tooltip or documented overflow;
- status chips do not imply a single flattened status field;
- audit/settings actions are discoverable but visually secondary to workflow
  context.

### 6.3 `Layout/SideNav`

Current node:

- Figma name: `Layout/SideNav`
- Node ID: `46:43`
- Spec alias: `Layout/WorkflowSidebar`
- Current readiness: skeleton
- Target code path:
  `frontend/src/shared/components/layout/WorkflowSidebar.tsx`

Target role:

`SideNav` expresses the hierarchy `Project -> Workflow -> Sessions in this
workflow`. It should make the selected workflow and selected session visible.

Required structure:

| Zone | Required content |
|---|---|
| Header | `Workflow`, `新会话` action |
| Workflow list | selected `任务规划与执行`, other modes such as `调研与结果卡`, `Bug 修复`, `结果验收` |
| Session group | `Sessions in this workflow` |
| Session items | `个人网站项目规划`, `产品介绍页`, `博客迁移` |
| Helper hint | concise explanation of Workflow vs Session, if space allows |

Required states/variants:

- expanded;
- collapsed;
- selected item;
- disabled item;
- empty;
- loading.

Token targets:

- selected item: `color/primitive/clear-blue` or semantic selected surface;
- borders: `color/semantic/border`;
- helper text: `color/semantic/text-secondary`;
- selected text/action: `color/semantic/action-primary`;
- use `Base/Button`, `Base/Badge`, and `Base/EmptyState` as instances.

Responsive notes:

- desktop: 272-288px expanded width;
- tablet: collapse to icon/compact rail before truncating main content;
- mobile: stack above main content or appear as a compact workflow selector;
  Drawer remains deferred.

Acceptance:

- hierarchy is readable without metadata notes;
- selected workflow and selected session are distinct;
- empty and loading states reserve stable height and do not shift main layout;
- no item depends on color alone to express selection.

### 6.4 `Layout/MainWorkArea`

Current node:

- Figma name: `Layout/MainWorkArea`
- Node ID: `46:76`
- Spec alias: `Layout/WorkbenchGrid`
- Current readiness: skeleton
- Target code path: `frontend/src/shared/components/layout/WorkbenchGrid.tsx`

Target role:

`MainWorkArea` is where the user understands and controls work. It must keep
TaskTree central while allowing message/process and result/file surfaces to
support the primary object.

Required structure:

| Zone | Required content |
|---|---|
| Workbench header | current task/session title and state badge |
| Primary region | TaskTree or selected work object |
| Supporting region | messages, result summary, or file summary depending state |
| Inline state region | loading, empty, error, stale, or permission summary |

Required states/variants:

- default / ready;
- loading;
- empty;
- error;
- stale;
- split-panel mode.

Semantic examples:

- empty: no TaskTree, show goal prompt affordance;
- planning: TaskTree skeleton plus process message;
- draft ready: personal website TaskTree with suggested/ready nodes;
- running: queued/running/done distribution;
- result/file: result summary plus file-change entry;
- stale: last-known content dimmed with resync action.

Token targets:

- primary surface uses `color/semantic/surface`;
- selected/active surfaces use selected semantic token or `clear-blue`;
- warning/running uses warning token or `wisdom-gold`;
- error state uses `Base/ErrorState` with danger tone supplied by owner;
- loading uses `Base/Skeleton`.

Responsive notes:

- desktop: multi-panel grid with stable width and no horizontal overflow;
- tablet: supporting region stacks below primary region;
- mobile: primary region first, supporting region below, input remains
  reachable.

Acceptance:

- TaskTree reads as the central object in default/draft/running examples;
- support content does not dominate the primary region;
- loading/empty/error/stale states are visually distinct;
- no generic `Default panel` text remains.

### 6.5 `Layout/DetailPanel`

Current node:

- Figma name: `Layout/DetailPanel`
- Node ID: `48:72`
- Current readiness: skeleton
- Target code path: `frontend/src/shared/components/layout/DetailPanel.tsx`

Target role:

`DetailPanel` is a dynamic context inspector. It should not behave like a
generic right card; it must show details for the currently selected workflow,
session, task, confirmation, result, file change, or audit entry.

Required structure:

| Zone | Required content |
|---|---|
| Header | detail kind, selected object title, status badge |
| Body | structured facts and current explanation |
| Related items | messages, files, evidence links, or result references |
| Actions | context-safe actions such as edit, preview, view audit, return |

Required states/variants:

- empty;
- selected task;
- session/workflow;
- result;
- audit entry;
- loading;
- error;
- stale;
- permission denied;
- readonly.

Semantic examples:

- workflow setup: `当前模式：Task Planning & Execution`;
- selected task: `设计页面结构`, parent `信息架构`, capability `ui.planning`;
- confirmation: `需要确认文件创建动作`, impact file list;
- result: `页面结构方案已完成`;
- file/audit: file summary and `查看这个任务的执行记录`;
- permission denied: safe reason and return action.

Token targets:

- detail surface uses `color/semantic/surface`;
- section dividers use `color/semantic/border`;
- metadata uses `type/muted`;
- status badges use tones from canonical dimensions;
- error/permission/stale use `Base/ErrorState`.

Responsive notes:

- desktop: 340-380px right inspector;
- tablet: inspector stacks below main or becomes a secondary column;
- mobile: inspector appears after selected primary content; no Drawer until
  drawer behavior is formalized.

Acceptance:

- selected state clearly ties to a selected object;
- confirmation/result/file/audit examples are distinguishable;
- long titles and file paths wrap or truncate without overlap;
- panel body scrolls independently when content is long.

### 6.6 `Layout/ContextInputBar`

Current node:

- Figma name: `Layout/ContextInputBar`
- Node ID: `48:134`
- Spec alias: `Layout/BottomInputDock`
- Current readiness: skeleton
- Target code path: `frontend/src/shared/components/layout/BottomInputDock.tsx`

Target role:

`ContextInputBar` makes natural-language input useful by making the target
scope explicit. The user must know whether the input affects the session,
selected task, clarification, or confirmation.

Required structure:

| Zone | Required content |
|---|---|
| Scope badge | `作用域：当前会话` or `作用域：任务：设计页面结构` |
| Mode label | `目标输入`, `任务补充`, `澄清回答`, `确认回应`, `只读` |
| Input surface | TextArea or Input with mode-specific placeholder |
| Action area | send/confirm/cancel/retry as applicable |
| Status/help | disabled reason, submitting state, validation error |

Required states/variants:

- goal input;
- task instruction;
- clarification answer;
- confirmation response;
- disabled/readonly;
- loading/submitting;
- error.

Semantic copy:

- session: `描述你想完成的事，例如：帮我规划一个个人网站项目`;
- task: `正在补充当前任务：设计页面结构`;
- clarification: `补充目标用户或内容范围`;
- confirmation: `确认执行、先预览、修改任务或跳过`;
- disabled: `当前为只读状态，不能提交新指令`;
- submitting: `正在发送`;
- error: `发送失败，可以重试`;

Token targets:

- input surface uses `Base/TextArea` and `color/semantic/surface`;
- scope/mode badges use `Base/Badge`;
- primary send action uses `Base/Button`;
- disabled and error states use standard component states, not custom colors;
- focus uses `shadow/focus`.

Responsive notes:

- desktop: bottom dock remains visible inside AppShell;
- tablet: dock width follows main content and avoids covering DetailPanel;
- mobile: dock remains reachable at bottom; action buttons may collapse to
  icon buttons with accessible labels.

Acceptance:

- user can identify input target without reading metadata;
- disabled/submitting/error states are visually distinct;
- placeholder wraps safely and does not overlap actions;
- keyboard/focus behavior is documented in component note.

## 7. Page-Level Figma Upgrade Plan For P4.11

The next Figma task should run in small batches and verify after each batch.

Batch 1:

- `Layout/AppShell`
- `Layout/TopBar`

Batch 2:

- `Layout/SideNav`
- `Layout/MainWorkArea`

Batch 3:

- `Layout/DetailPanel`
- `Layout/ContextInputBar`

For each batch:

1. pre-check existing node IDs and note frames;
2. preserve existing node IDs where possible;
3. upgrade visual content and semantic examples;
4. update component note text and readiness status;
5. verify no overlap and no placeholder copy;
6. attempt screenshot-width verification at 1600px;
7. stop on Figma MCP timeout or node identity loss.

## 8. Acceptance Criteria

The P4.11 Figma upgrade is acceptable only if:

- `04 - Layout Components` no longer reads as a generic skeleton page;
- all six layout components use product-real example content;
- no old Figma frames are copied or bulk-migrated;
- existing component names remain stable;
- node IDs are preserved unless an explicit blocker explains why not;
- generic labels such as `Primary`, `Neutral`, `Default panel`, and
  `Panel container skeleton` are removed from visible production examples;
- all visual values are token-backed or clearly marked as token blockers;
- AppShell shows the full workbench composition;
- TopBar shows product/project/workflow/session/status/actions;
- SideNav shows workflow/session hierarchy;
- MainWorkArea keeps TaskTree visually central;
- DetailPanel behaves as a context inspector;
- ContextInputBar makes input scope visible;
- responsive notes cover desktop, tablet, and mobile without relying on
  Drawer;
- Figma notes state that upgraded components are visually aligned drafts, not
  frontend implementation;
- screenshot or structural verification confirms no major overlap, clipping,
  or horizontal overflow.

## 9. Known Blockers And Decisions

| Item | Status |
|---|---|
| Product mark asset | Needs final top-bar binding check before visual sign-off. |
| Drawer behavior | Explicitly deferred; do not use for responsive layout in this pass. |
| Audit shell visual direction | Deferred to Audit visual baseline work after Main/layout upgrade. |
| Final frontend paths | P5 architecture may resolve aliases such as `SideNav` vs `WorkflowSidebar`, `MainWorkArea` vs `WorkbenchGrid`, and `ContextInputBar` vs `BottomInputDock`. |
| Screenshot transport | Must be attempted in P4.11; transport failure should be recorded separately from structural verification. |

## 10. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.
Use the plato-figma-governance skill next.

Task:
Upgrade governed Figma Layout Components on canonical page 04 - Layout Components
using docs/design/layout-components-visual-upgrade-brief.md.

Do not create domain components, screen states, prototype interactions, or
frontend code. Preserve existing component names and node IDs where possible.
Use existing tokens and Base Components. Do not copy old Figma frames. Replace
generic skeleton copy with product-real sample content. Verify each batch.
```
