# Plato Figma UI Baseline

> Status: historical/reference Figma baseline 1.0
>
> Target file: <https://www.figma.com/design/wHFPOBaxeImyhJer7BnMaq>
>
> Generated: 9 desktop Main Page state frames plus one review notes frame.
>
> Revision: v0.2 clarifies `Project -> Workflow -> Session -> Session Workspace` and fixes text overflow.

> Governance note: this baseline is now reference/archive input. New canonical
> Figma work must happen in `Plato Product Design System and Prototype` and
> follow `docs/design/figma-governance.md`.

## 1. Objective

Generate a desktop-first Figma UX draft for Plato's MVP Main Page.

The draft should express the product's core interaction model:

```text
Natural language goal
  -> Project
  -> Workflow
  -> Session
  -> Session Workspace
  -> Understanding
  -> Draft TaskTree
  -> TaskNode selection and refinement
  -> Publish and execution
  -> Confirmation
  -> Result
  -> File Change Summary
  -> Audit entry
```

The output should prioritize object clarity over visual perfection.

## 2. Product Positioning

Plato is a Task-first intelligent workbench.

It is not:

- a Todo app,
- a raw chat UI,
- a terminal,
- an IDE,
- a full workflow engine.

It is a calm, structured control plane where ordinary users can understand,
adjust, confirm, execute, and review AI-generated work.

## 3. Visual Direction

Style:

```text
Modern Classical Workbench
```

Traits:

- calm,
- structured,
- legible,
- rational,
- trustworthy,
- restrained.

Avoid:

- cyber / neon AI styling,
- large gradients,
- glassmorphism,
- ancient Greek decoration as persistent UI,
- marketing hero layout,
- cards nested inside cards,
- playful oversized rounded UI.

## 4. Color Direction

Use restrained blue / gold / cream / gray.

Recommended tokens:

| Token | Use | Color |
|---|---|---|
| ink | Main text | `#172033` |
| graphite | Secondary text and icons | `#5E6878` |
| line | Borders and dividers | `#DCE3ED` |
| surface | Page background | `#F7F9FC` |
| panel | Panel background | `#FFFFFF` |
| reason-blue | Brand and primary action | `#2B5CAA` |
| clear-blue | Selected / hover | `#5B8FD9` |
| mist-blue | Light selected background | `#E8F1FB` |
| wisdom-gold | Attention / running | `#D4A137` |
| cream | Gentle empty states | `#F5F2EC` |
| success | Done / ready | `#4F7D5A` |
| warning | Waiting user | `#B86E2F` |
| danger | Failure / high risk | `#B94A48` |

## 5. Typography

Detailed type roles and text color semantics are defined in
[Typography System](../design/typography-system.md). This section is the
visual baseline summary for Figma composition.

Use a modern readable sans-serif.

Preferred:

- Inter for English and UI numerals.
- Noto Sans SC / Source Han Sans / PingFang SC for Chinese if available.

Workstation UI text should be compact but readable.

Do not use hero-scale typography inside panels.

## 6. Core Layout

Create a stable desktop workbench frame, 1440 x 1024.

Suggested structure:

```text
+--------------------------------------------------------------+
| Top Bar: Plato / Project / Workflow / Session / Status        |
+----------------------+----------------------+----------------+
| Workflow + Sessions  | Main Work Area       | Detail Panel   |
|                      | TaskTree / Messages  | Context info   |
|                      | Session Workspace   | Result / Files |
+----------------------+----------------------+----------------+
| Context-aware input: session-level or task-scoped             |
+--------------------------------------------------------------+
```

The TaskTree should remain visually central. Message stream should support the
process but not dominate the page.

Navigation should express hierarchy:

```text
Project
  -> Workflow
      -> Sessions in this workflow
```

The execution workspace is session-scoped by default. The UI can show this as a
lightweight hint such as `Session workspace: isolated`; it should not make the
workspace itself the user's primary object.

The Detail Panel is dynamic. It should behave as a Context Inspector:

- Before a session starts: Workflow information and start affordance.
- During understanding/planning: Session goal and progress.
- During review/editing: selected TaskNode detail.
- During confirmation: confirmation card for the selected TaskNode.
- After completion: result, summary, file changes, and audit entry.

## 7. Required Frames

Generated 9 frames in the same Figma file.

Use names exactly:

1. `S1 - Empty New Session`
2. `S2 - Understanding`
3. `S3 - Draft TaskTree Ready`
4. `S4 - TaskNode Selected`
5. `S5 - TaskNode Editing`
6. `S6 - Published Running`
7. `S7 - Waiting For Confirmation`
8. `S8 - Completed With Result`
9. `S9 - File Change Summary Audit Entry`

Arrange frames in a 3 x 3 grid, each 1440 x 1024, with 120px gap.

Generated frame IDs:

| Frame | Node ID |
|---|---|
| `S1 - Empty New Session` | `6:2` |
| `S2 - Understanding` | `6:65` |
| `S3 - Draft TaskTree Ready` | `6:145` |
| `S4 - TaskNode Selected` | `6:266` |
| `S5 - TaskNode Editing` | `6:391` |
| `S6 - Published Running` | `6:519` |
| `S7 - Waiting For Confirmation` | `6:641` |
| `S8 - Completed With Result` | `6:761` |
| `S9 - File Change Summary Audit Entry` | `6:874` |
| `Plato UX Draft Notes` | `6:999` |

## 8. Shared Screen Elements

Every frame should include:

- Product mark: `柏拉图 Plato`
- Current project: `Personal Website`
- Workflow chip: `Task Planning & Execution`
- Session title: `个人网站项目规划`
- Session status
- Session workspace isolation hint
- TaskTree / WorkTree area
- Session message area
- Detail panel
- Context-aware input

## 9. Sample TaskTree

Use this sample task structure:

```text
个人网站项目规划
├─ 需求分析
│  ├─ 明确目标用户
│  └─ 梳理内容范围
├─ 信息架构
│  ├─ 设计页面结构
│  └─ 定义导航
├─ 视觉方向
│  ├─ 确定风格关键词
│  └─ 选择配色与字体
├─ 开发实现
│  ├─ 初始化项目
│  ├─ 实现首页
│  └─ 响应式适配
└─ 验收与发布
   ├─ 检查文件变更
   └─ 准备发布说明
```

TaskNode states to show across frames:

- Proposed
- Ready
- Queued
- Running
- Waiting for Confirmation
- Done
- Failed

## 10. Frame Specs

### S1 - Empty New Session

Purpose:

User enters Plato for the first time.

Show:

- Empty TaskTree area.
- Clear natural language input.
- Weak audit entry.
- Default Workflow selected.

Input placeholder:

```text
描述你想完成的事，例如：帮我规划一个个人网站项目
```

### S2 - Understanding

Purpose:

User submitted a goal; system is interpreting.

Show:

- Status: `正在理解目标`
- User goal visible.
- TaskTree skeleton or planning state.
- Message: `正在把你的目标整理成可执行的任务结构。`

### S3 - Draft TaskTree Ready

Purpose:

Draft TaskTree is generated and awaits review.

Show:

- Status: `Reviewing`
- TaskTree state: `Draft`
- Main action: `发布任务`
- TaskNodes with Proposed / Ready states.
- Message: `已生成任务计划，你可以先审阅再执行。`

### S4 - TaskNode Selected

Purpose:

User selects a TaskNode.

Selected node:

```text
设计页面结构
```

Show detail panel:

- Title
- Intent
- Status: Ready
- Parent: 信息架构
- Related messages
- Expected result
- Capability: `ui.planning`

Input placeholder:

```text
正在补充当前任务：设计页面结构
```

### S5 - TaskNode Editing

Purpose:

User adds task-scoped instructions.

Show:

- Selected TaskNode remains highlighted.
- User message: `首页需要突出个人介绍和项目作品，不要做得太复杂。`
- System update: `已将这条补充加入当前任务。`
- TaskNode state: Updated / Ready.

### S6 - Published Running

Purpose:

User published the Draft TaskTree; tasks are executing.

Show:

- TaskTree status: Published / Executing.
- Some TaskNodes queued, running, done.
- Publish button replaced by running state.
- Message stream shows execution updates.

Example states:

- 需求分析: Done
- 信息架构: Running
- 视觉方向: Queued
- 开发实现: Queued
- 验收与发布: Queued

### S7 - Waiting For Confirmation

Purpose:

System needs user confirmation for a specific TaskNode.

TaskNode:

```text
初始化项目
```

Show Confirmation Card:

- Title: `需要确认文件创建动作`
- Context: `此任务将创建项目结构和配置文件。`
- Impact:
  - `package.json`
  - `src/App.tsx`
  - `src/styles.css`
- Options:
  - `确认执行`
  - `先预览`
  - `修改任务`
  - `跳过此任务`

This confirmation must be visually attached to the TaskNode, not a detached modal.

### S8 - Completed With Result

Purpose:

A TaskNode completed and result is available.

TaskNode:

```text
设计页面结构
```

Show Result Card:

- Title: `页面结构方案已完成`
- Summary:
  - 首页包括个人介绍、作品精选、联系方式。
  - 导航保持三项以内。
  - 后续开发任务可以直接使用此结构。
- Actions:
  - `查看文件变更`
  - `继续追问`
  - `创建后续任务`
  - `查看审计`

### S9 - File Change Summary Audit Entry

Purpose:

User reviews changes and sees trust entry.

Show:

- File Change Summary for selected TaskNode.
- Parent aggregation note.
- Audit entry.

Files:

| File | Change | Summary |
|---|---|---|
| `docs/site-structure.md` | created | 记录页面结构方案 |
| `docs/content-outline.md` | modified | 增加首页内容大纲 |
| `docs/navigation.md` | created | 定义导航结构 |

Audit entry:

```text
查看这个任务的执行记录
```

## 11. Component Direction

Create editable visual components as needed:

- `TaskNodeItem`
- `TaskTreePanel`
- `SessionMessage`
- `ConfirmationCard`
- `ResultCard`
- `FileChangeSummary`
- `ContextInput`
- `StatusBadge`

Components do not need to be perfect reusable Figma components in the first pass,
but layer names should be clear enough for later extraction.

## 12. Figma Generation Prompt

Use this prompt for the actual generation:

```text
Create a desktop-first Figma UX draft for Plato, a Task-first intelligent workbench.

Use a Modern Classical Workbench style: calm, structured, legible, rational,
trustworthy, with restrained blue/gold/cream/gray colors, fine borders, stable
grids, subtle shadows, and 8px-or-less corner radius. Avoid neon AI styling,
glassmorphism, ancient Greek decorative UI, marketing hero layouts, and nested cards.

Generate 9 frames, each 1440x1024, arranged in a 3x3 grid:
S1 Empty New Session,
S2 Understanding,
S3 Draft TaskTree Ready,
S4 TaskNode Selected,
S5 TaskNode Editing,
S6 Published Running,
S7 Waiting For Confirmation,
S8 Completed With Result,
S9 File Change Summary Audit Entry.

Every frame should share a stable workbench structure:
Top Bar with Plato, workspace, workflow, session, and status.
Navigation/session side area.
Main work area where TaskTree remains central.
Detail panel for selected TaskNode, messages, result, files, and audit.
Bottom context-aware natural language input.

Use the personal website project sample TaskTree and show TaskNode state changes
across the frames. Make confirmation actions visibly attached to the relevant
TaskNode. Make Result and File Change Summary stable objects, not just chat
messages. Keep Audit as a trust entry, not the main workflow.
```

## 13. Review Criteria

The generated design is acceptable if a first-time user can answer:

1. Which Workflow and Session am I in?
2. What did Plato understand my goal to be?
3. Where is the TaskTree?
4. Which TaskNode needs my attention?
5. What does the input box affect right now?
6. Has execution started or is this still draft?
7. What am I being asked to confirm?
8. Where is the result?
9. What files changed?
10. Where can I inspect the audit trail?
