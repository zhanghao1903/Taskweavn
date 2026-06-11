# AI-Assisted Project Failure Memo

> Date: 2026-06-01
> Status: discussion memo / draft
> Scope: one-month Taskweavn / Plato AI-assisted project retrospective
> Purpose: collect failure cases first; detailed event-by-event review can be
> written later.

---

## 1. Why This Memo Exists

This memo records failure patterns from one month of building Plato / Taskweavn
with AI assistance.

It is intentionally not a final retrospective. The goal is to create a working
memory of failure cases before they are softened into abstract lessons.

The current framing:

- the project still has value as an AI product / PM case study;
- Product 1.0 is not fully closed yet;
- several major problems came from process, sequencing, and source-of-truth
  gaps rather than raw coding ability.

---

## 2. Initial Failure Inventory

### F1. Figma work consumed too much time with low ROI

Observation:

- A large amount of time went into Figma file creation, governance, token setup,
  component skeletons, screen states, prototype flows, and hygiene passes.
- The resulting design quality and implementation usefulness were not
  proportional to the effort.
- Static historical drafts ended up being more useful as visual baselines than
  the governed canonical component/prototype work.

Likely causes:

- treated Figma productionization as a required upstream artifact too early;
- overestimated the value of componentized Figma structure before frontend
  architecture was stable;
- spent too much energy making Figma governable instead of making the product
  path demonstrable;
- underestimated how hard it is for AI-assisted Figma operations to maintain
  visual fidelity and layout hygiene.

Potential lesson:

- For early AI product exploration, use Figma as a visual/reference baseline,
  not as the primary implementation source.
- Do not invest in full Figma design-system production until state model,
  interaction model, and frontend architecture are stable.

### F2. Frontend implementation started before key models existed

Observation:

- Early frontend work lacked a canonical status model, screen-state model,
  interaction model, API/UI mapping, and frontend architecture plan.
- This caused Main Page implementation churn, controller extraction, status
  mapping refactors, route/runtime wrappers, and repeated architecture recovery.

Likely causes:

- implementation started from static screens and mock states rather than stable
  ViewModel contracts;
- "make the page visible" outran "define what states the page must represent";
- frontend component extraction happened before clear ownership boundaries.

Potential lesson:

- For state-heavy Agent products, frontend work must start from:
  - canonical status dimensions;
  - screen state spec;
  - event/reducer contract;
  - API-to-UI mapping;
  - route/runtime ownership boundaries.
- Visual implementation without state architecture creates expensive rework.

### F3. Product workflow was not hardened early enough

Observation:

- The PRD -> UX spec -> Figma -> review -> frontend architecture -> API/mock ->
  backend integration workflow was not enforced at the start.
- Work sometimes jumped ahead while upstream dependencies were missing or weak.
- When the human did not catch the missing dependency, later work became
  fragile or misdirected.

Likely causes:

- workflow existed as an idea but was not codified into agent instructions and
  repo docs early enough;
- AI sessions optimized for local task completion rather than global product
  sequencing;
- missing dependency checks were manual instead of systematic.

Potential lesson:

- Workflow gates must be part of the agent operating contract, not just a
  planning preference.
- Missing upstream artifacts should block implementation or force the smallest
  explicit draft artifact first.

### F4. Docs directory restructuring regressed the project

Observation:

- A docs directory restructuring was requested without fully specifying the
  desired information architecture and migration constraints.
- The result was worse than the previous structure and caused project
  regression risk.
- A backup branch prevented a larger accident.

Likely causes:

- requirements were under-specified;
- the target doc taxonomy was not reviewed before bulk moves;
- migration safety rules and acceptance criteria were not strict enough;
- AI-assisted broad restructuring is high risk when the source-of-truth graph is
  already complex.

Potential lesson:

- Never do broad docs restructuring without:
  - a target tree proposal;
  - source-of-truth rules;
  - migration map;
  - backup branch;
  - diff review;
  - rollback plan.

---

## 3. Additional Failure Patterns To Review

### F5. Overestimated TaskBus and orchestration value

Observation:

- The initial product imagination centered on multi-Agent orchestration and
  TaskBus-based coordination.
- Real usage pressure moved the product toward a Codex-like single workbench and
  fixed-route execution.
- TaskBus remains useful as durable lifecycle authority, but its value as an
  orchestration brain was overestimated.

Potential lesson:

- In Product 1.0, TaskBus should be a fact ledger and lifecycle authority, not a
  product centerpiece.
- Multi-Agent routing should wait until context continuity and evidence
  governance are strong enough.

### F6. DFX was discovered late

Observation:

- Durability, feedback, recoverability, and explainability were not treated as
  first-class product requirements from the beginning.
- Missing RawTask / DraftTaskTree persistence broke the user main path after
  restart.
- DFX became important only after data loss exposed the failure.

Potential lesson:

- For Agent products, DFX is not polish. It is the product foundation.
- "Can resume after restart" should be a Product 1.0 acceptance criterion from
  the beginning.

### F7. Context management was treated as advanced architecture instead of main-path continuity

Observation:

- Context Manager became visible only after persistence and restart issues.
- The project first focused on Agent/task orchestration, while the actual hard
  problem was preserving useful context across steps, tasks, retries, and
  restarts.

Potential lesson:

- Agent lifecycle and context lifecycle must be separated early.
- Context should be designed as user/work continuity, not only as prompt
  optimization.

### F8. Product positioning and commercialization were considered too early

Observation:

- The project carried platform/product/commercialization assumptions before the
  core user path was closed.
- Later evaluation shifted toward employment-market demonstration and AI PM /
  technical PM case-study value.

Potential lesson:

- Before commercial positioning, prove:
  - one stable user path;
  - one clear user segment;
  - one repeatable demo;
  - one credible differentiation.
- Until then, frame the work as product discovery and capability evidence.

### F9. Demo and product smoke were not treated as the primary truth

Observation:

- Many tests, docs, and contracts were completed before a stable user-facing
  demo became the dominant acceptance standard.
- Scenario tests and contract tests helped, but did not fully answer whether the
  product path felt real.

Potential lesson:

- For portfolio/product validation, a stable demo path is higher leverage than
  broad internal scenario coverage.
- Product 1.0 should define a small number of manual smoke paths and keep them
  green.

### F10. AI sessions optimized for local completion, not cumulative product judgment

Observation:

- Individual sessions often made progress locally but could miss broader product
  sequencing, previous decisions, or cross-doc consistency.
- This caused repeated rediscovery, status drift, and occasional overwork in the
  wrong layer.

Potential lesson:

- Long-running AI-assisted projects need:
  - explicit workflow gates;
  - current roadmap/gap registry;
  - durable decision records;
  - small slice boundaries;
  - end-of-session status updates.

### F11. Scope control improved late

Observation:

- Product 1.0 / 1.1 separation became clearer only after several rounds of
  overreach.
- Features such as routing foundation, Result Packaging, context governance,
  skills/MCP, and multi-Agent expansion were eventually moved out of Product
  1.0.

Potential lesson:

- Scope boundaries should be reviewed after every major architecture discovery.
- If a capability does not directly close the main user path, it should default
  to Product 1.1+.

### F12. Case-study value was recognized late

Observation:

- The project was initially judged mostly as a commercial product or engineering
  system.
- Later it became clearer that the strongest near-term value may be PM /
  technical PM evaluation: product definition, system thinking, state modeling,
  execution closure, and judgment under uncertainty.

Potential lesson:

- If the goal shifts to employment-market evaluation, prioritize:
  - clear narrative;
  - stable demo;
  - case-study write-up;
  - decision trail;
  - visible product judgment.

---

## 4. Cross-Cutting Root Causes

Current hypothesis:

1. Architecture attractiveness outran product evidence.
2. Visual/design tooling work outran state and interaction modeling.
3. Implementation outran frontend architecture.
4. Workflow governance was added after the project had already accumulated
   process debt.
5. DFX was treated as infrastructure rather than user-path product value.
6. AI agents needed stronger source-of-truth and dependency gates.
7. The product goal changed from commercial product to portfolio/case-study
   evidence, but the work plan took time to reflect that.

---

## 5. Candidate Follow-Up Retrospectives

Each item below can become a focused event review:

1. Figma ROI failure.
2. Frontend architecture rework.
3. Missing workflow gate and upstream dependency failures.
4. Docs directory restructuring regression.
5. RawTask / DraftTaskTree persistence incident.
6. TaskBus and orchestration overestimation.
7. Context Manager / DFX discovery.
8. Product 1.0 / 1.1 scope reset.
9. Main Page and fixed-route closure.
10. Employment-market positioning shift.

Suggested review template:

```text
Event:
Original assumption:
What happened:
Impact:
Root cause:
What AI did well:
What AI did poorly:
What the human missed:
Preventive rule:
Future workflow change:
```

---

## 6. Open Questions

- Which failures were caused by AI assistance, and which were normal product
  discovery costs?
- Which workflow gates should be mandatory for future AI-assisted projects?
- What should be the minimum artifact set before frontend implementation starts?
- When should Figma be used as high-fidelity design source versus visual
  reference only?
- How much architecture is enough before a stable demo path exists?
- What DFX requirements must be Product 1.0 defaults for any Agent product?
- How should the project be narrated for AI PM / technical PM evaluation?
