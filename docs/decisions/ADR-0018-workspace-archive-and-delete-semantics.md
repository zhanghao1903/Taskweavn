# ADR-0018: Workspace Archive And Delete Semantics

> Status: accepted
> Date: 2026-06-11
> Related: [Workspace Entry Contract](../engineering/workspace-entry-contract.md), [Multi-workspace API Runtime Contract](../engineering/multi-workspace-api-runtime-contract.md), [Token Usage Analytics Contract](../engineering/token-usage-analytics-contract.md), [Workspace Archive, Delete, And Settings Data Management](../plans/feature/workspace-archive-delete-data-management.md)

---

## Context

Plato is now a workspace-first desktop app. A workspace is a user-selected local
folder. Plato stores product-owned state under the workspace's hidden metadata
root:

```text
<workspace>/.plato/
```

The same product area now needs three related but different user intents:

1. stop seeing a workspace in the everyday sidebar;
2. restore a previously hidden workspace;
3. clean up files that Plato created inside a workspace.

A separate "remove" action would create a third user-facing lifecycle word
beside "archive" and "delete". That is unnecessary learning cost.

---

## Decision

Plato will expose two user-facing workspace lifecycle actions:

```text
Archive workspace
Delete Plato data
```

There is no separate user-facing "remove workspace" action.

### Archive Workspace

Archive means:

- hide the workspace from Main Page's normal workspace sidebar;
- exclude the workspace from the sidecar workspace registry and default
  `GET /api/v1/workspaces` catalog;
- keep the workspace folder, user files, `.git`, and `.plato` unchanged;
- allow restore from Settings -> Data Management;
- also restore automatically if the user opens the same folder again.

Archive is a visibility and focus-management action. It is reversible and does
not modify workspace-local Plato state.

### Delete Plato Data

Delete means:

- delete Plato-owned metadata for that workspace;
- remove the workspace from the app-level workspace registry;
- keep the workspace folder and user project files;
- keep `.git` and repository history;
- do not expose a recoverability promise after the delete succeeds.

The delete target is:

```text
<workspace>/.plato/
```

The cleanup may also include legacy Plato metadata roots when present:

```text
<workspace>/.taskweavn/
<workspace>/.code-agent/
```

The action must not be named "Delete workspace" because Plato does not delete
the user's project directory.

---

## Ownership Boundary

Electron main owns workspace lifecycle actions because it already owns:

- raw local workspace paths;
- the native folder picker;
- the app-level recent/current workspace registry;
- sidecar start/stop and renderer reload.

Python sidecar owns workspace-internal product stores for an already-opened
workspace. It must not become the general local folder deletion authority.

Renderer receives only safe workspace summaries and action results.

---

## Settings Information Architecture

Settings becomes a tabbed modal with three top-level tabs:

1. **Configuration**
   - LLM provider/model/API key;
   - logging profile;
   - interface language;
   - Git initialization preference.
2. **Data Management**
   - current/recent workspaces;
   - archived workspaces;
   - archive, restore, and delete Plato data actions.
3. **Usage Information**
   - token usage summaries and cache hit-rate visibility.

Workspace restore belongs in Data Management because it is a lifecycle/data
visibility operation, not part of the Main Page working surface.

Token Usage belongs in Usage Information. Main Page must not keep a first-level
Workspace Usage navigation button. Deep links and contextual detail metrics may
remain where useful, but Settings is the canonical user entry for browsing usage
information.

---

## Consequences

Positive:

- Users learn two verbs instead of three.
- Archive is safely reversible.
- Delete explicitly manages files Plato created and avoids hidden metadata
  garbage in a workspace.
- The raw path and file-deletion boundary remains in Electron main.
- Settings becomes the single management surface for configuration, data, and
  usage.

Tradeoffs:

- Archive requires app-level registry schema support.
- Deleting current workspace data must stop or restart the sidecar before
  touching `.plato`.
- A user who wants a pure "forget this path but keep `.plato`" gets Archive
  instead. This is intentional; it preserves a restore path and avoids another
  lifecycle word.
- Existing Git local exclude entries for `.plato/` may remain after deletion
  unless a future implementation can identify a Plato-owned marker safely.

---

## Deferred Decisions

- Whether to add an Archived Workspaces count/badge outside Settings.
- Whether to support permanent deletion when OS Trash is unavailable.
- Whether future cloud/sync workspaces need separate archive semantics.
- Whether to add a Plato-owned marker around `.git/info/exclude` lines for
  safer cleanup of Git local exclude entries.
