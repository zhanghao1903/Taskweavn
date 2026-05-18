# UI Visual Reference

> Status: superseded visual reference
> Last Updated: 2026-05-17
> Scope: Task-first UI visual exploration  
> Note: These images are not final design specs. The current visual source is the Figma UI baseline 1.0 in [Plato Figma UI Baseline](../../product/plato-figma-ui-baseline.md).

---

## 1. Purpose

This document indexes historical UI sketches and prototype screenshots under `docs/plans/ui/images/`.

The textual plans remain the source of truth for concepts, APIs, and interaction rules. The images serve as visual references for:

- early main page layout exploration;
- early Task card shape exploration;
- Task map / topology exploration;
- hand-drawn information structure.

---

## 2. Image Index

| Image | Working Meaning |
|---|---|
| [hand draw.jpeg](images/hand%20draw.jpeg) | Early hand-drawn concept sketch. |
| [Taskwean main page 00_04_17.png](images/Taskwean%20main%20page%2000_04_17.png) | Main page visual exploration, version 1. |
| [Taskwean main page 00_04_34.png](images/Taskwean%20main%20page%2000_04_34.png) | Main page visual exploration, version 2. |
| [Taskwean Taskcard.png](images/Taskwean%20Taskcard.png) | Task card interaction shape exploration. |
| [Taskwean Task map 00_05_55.png](images/Taskwean%20Task%20map%2000_05_55.png) | Task map / topology exploration. |

---

## 3. How To Use These Images

- Treat them as product direction, not pixel-final design.
- Use them to validate whether the document model is visually plausible.
- When a visual detail conflicts with the written API/interface design, update the written plan first, then revise the visual.
- Keep future images in this folder and add them to the index above.

---

## 4. Current Interpretation

The current visual direction supports the existing Task-first design:

- The main page is centered around Task work, not a plain chat timeline.
- Task cards should expose status, user actions, and task-scoped information in one place.
- Task topology needs a dedicated view, because a Session can contain many Tasks.
- Session messages still exist, but they should support Task filtering and contextual projection.

---

## 5. Related Plans

- [Task-first UI overview](../task-first-ui-interaction.md)
- [Information architecture](information-architecture.md)
- [Task tree view](task-tree-view.md)
- [Task node detail](task-node-detail.md)
- [Task message view](task-message-view.md)
- [Task domain/UI model separation](../feature/task-domain-ui-model-separation.md)
