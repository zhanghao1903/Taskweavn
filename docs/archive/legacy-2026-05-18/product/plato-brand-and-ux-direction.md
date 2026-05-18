# Plato Brand And UX Direction

> Status: UX direction seed
>
> Scope: product naming, emotional tone, and interaction direction. This
> document does not rename Python packages, repository paths, or internal
> architecture objects.

## 1. Product Name

The user-facing product name is:

```text
柏拉图 / Plato
```

The name refers to Plato, the ancient Greek philosopher.

This name should guide the product's external feeling, not force every internal
system object to become philosophical metaphor. The product can keep precise
technical names internally while presenting a more human, thoughtful product
surface to users.

## 2. Naming Boundary

There are now three possible naming layers:

| Layer | Name | Purpose |
|---|---|---|
| Product brand | 柏拉图 / Plato | What users see and remember. |
| Project / repo / package | TaskWeavn / taskweavn | Current engineering identity and implementation namespace. |
| Domain objects | Workflow, Session, TaskTree, TaskNode, Agent, Result | Stable product and architecture concepts. |

The first UX version should not rush into a full code rename.

Recommended boundary:

- UI title, product copy, onboarding, and marketing language use `柏拉图 / Plato`.
- Documentation can say "Plato is the user-facing product built on the TaskWeavn task system."
- Internal package names can remain `taskweavn` until the product architecture and distribution story are clearer.
- Core product objects should stay literal and understandable: Workflow, Session, Task, Result, Audit.

## 3. Product Meaning

The name `Plato` should connect to the product through the idea of structured
thinking.

The product does not merely answer. It helps the user transform unclear intent
into a visible structure:

```text
unclear intention
  -> dialogue and clarification
  -> structured TaskTree
  -> deliberate execution
  -> reviewable result
```

This is a good match for a Task-first product because the product's main value
is not speed alone. Its value is making work understandable, controllable, and
traceable.

## 4. Tone

The product tone should be:

- calm,
- thoughtful,
- precise,
- quietly capable,
- helpful without being theatrical,
- friendly without becoming cute,
- serious enough for real work,
- approachable enough for non-technical users.

Avoid:

- overly mystical philosophy language,
- heavy academic references,
- decorative ancient-Greece theming,
- making the user feel like they need to understand philosophy,
- hiding operational clarity behind metaphor.

The name can carry depth. The UI should still be plain and intuitive.

## 5. UX Direction

Plato should feel like a thinking workbench.

The main interaction is:

```text
Tell Plato what you want.
Plato turns it into Tasks.
You review, adjust, confirm, and run.
Plato keeps the process visible.
```

The user should feel:

- "I know what the system thinks my task is."
- "I can correct it before it acts."
- "I can see what is happening."
- "I know when I need to make a decision."
- "I can inspect the result and trust the process."

## 6. Main Page Implication

The Main Page should not feel like a terminal, IDE, or raw chat room.

It should feel like a control surface for thought turning into work:

- Workflow frames the mode.
- Session frames the current collaboration.
- TaskTree shows the structure.
- TaskNode anchors decisions and progress.
- Result shows what was produced.
- Audit remains available for trust, not primary operation.

## 7. Possible Product Language

These phrases are directionally aligned:

- "Turn intention into tasks."
- "Plan before execution."
- "See the work before it happens."
- "Shape the task, then let it run."
- "A visible path from idea to result."
- "Work with a system that shows its reasoning as tasks."

These phrases are less aligned:

- "Autonomous AI employee."
- "One-click do everything."
- "Replace your workflow."
- "The ultimate multi-agent system."
- "Philosophy-powered AI."

The stronger positioning is not that Plato is magical. It is that Plato is
legible.

## 8. Relationship To TaskWeavn

For now, treat `TaskWeavn` as the system or engine identity and `Plato` as the
product identity.

```text
Plato
  user-facing product
  built on
TaskWeavn
  Task-first agentic execution system
```

This split gives us room to evolve:

- If Plato becomes the only product name, we can later rename packages and docs.
- If TaskWeavn remains the engine, Plato can be the first product built on it.
- If multiple philosopher-named products emerge, TaskWeavn can remain the shared
  task substrate.

## 9. Open Questions

1. Should the English-facing product name be `Plato`, while Chinese UI uses
   `柏拉图`?
2. Should `TaskWeavn` remain visible to users at all, or only appear in developer
   docs?
3. Is Plato a single product, or the first product in a family of
   philosopher-named tools?
4. Should Workflow templates carry philosophical names, or should they stay plain
   and literal?
5. What visual tone should match the name without becoming decorative or
   academic?

## 10. Current Decision

Use `柏拉图 / Plato` as the user-facing product name for the UX design line.

Do not rename code, package paths, or architecture documents yet.

Keep the product grounded in the Task-first mental model:

```text
Workflow -> Session -> TaskTree -> TaskNode -> Result -> Audit
```
