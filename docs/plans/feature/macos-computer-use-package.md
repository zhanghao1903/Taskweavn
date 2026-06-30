# macOS Computer-Use Capability Package

> Status: Historical package plan. The original single-package
> `macos-computer-use` design was superseded by the published package suite:
> `app-control-protocol`, `computer-use-macos`, and `wechat-desktop-tool`.
> Current Plato migration work is tracked in
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md).
>
> Last Updated: 2026-06-19
>
> Related:
> [Local Computer-Use Tool Foundation](local-computer-use-tool.md),
> [App-Control Tool Package Migration](app-control-tool-package-migration.zh-CN.md),
> [App-Control Tool Package Smoke Runbook](app-control-tool-package-smoke-runbook.zh-CN.md),
> [Historical Technical Design](macos-computer-use-package-technical-design.zh-CN.md),
> [Remote WeChat Message Task PRD](../../product/remote-wechat-message-task-prd.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md),
> [Confirmation UI Spec](../../ux/confirmation-ui-spec.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md)

---

## 1. Problem

Plato needs a real local desktop automation capability for Product 1.1 proofs,
starting with macOS. The capability is useful outside Plato as well: other
Agent applications may want a small, LLM-free desktop automation package that
can observe, open apps, click safe targets, and type text behind explicit
permission and risk boundaries.

If the macOS implementation is built directly inside Taskweavn/Plato, it will
be harder to:

- publish and reuse it in other Agent applications;
- test its OS capability boundary independently;
- keep Plato-specific concepts such as TaskBus, Session, Confirmation UI, and
  Audit out of the low-level desktop automation layer;
- replace or version the backend cleanly.

## 2. Product Decision

Build the macOS computer-use capability as a standalone Python package first.
This section records the original single-package decision. It is no longer the
active package boundary.

Working package name:

```text
macos-computer-use
```

Python import package:

```python
import macos_computer_use
```

Current package boundary:

```text
app-control-protocol  -> shared ToolCommand / ToolObservation / ToolEvent
computer-use-macos    -> macOS app-control primitives and helper transport
wechat-desktop-tool   -> WeChat semantic desktop commands
```

Plato should later consume this package through a normal package dependency and
a narrow adapter. Plato must not vendor the package source or import it through
a repository-relative path.

This package is intentionally not an Agent framework. It provides local OS
capability only.

## 3. Package Boundary

In scope for the package:

- macOS readiness and permission checks;
- Accessibility-first structured observation;
- allowlisted app opening;
- semantic target resolution for low-risk click actions;
- focused editable text insertion;
- bounded wait operations;
- risk classification metadata;
- structured result and error models;
- safe diagnostic metadata;
- manual local smoke examples.

Out of scope for the package:

- LLM calls or model providers;
- AgentLoop, TaskBus, Session, Plan, TaskNode, Audit, or UI concepts;
- Plato-specific confirmation storage or rendering;
- WeChat-specific workflow policy;
- remote ExecutionEnv networking;
- business hooks;
- screenshot evidence storage;
- user credential entry;
- automatic message sending without caller-supplied confirmation authorization.

The package may return `confirmation_required` / `blocked` metadata, but the
caller owns the UI and durable confirmation lifecycle.

## 4. Public API Shape

Initial public API should be small and stable:

```python
from macos_computer_use import MacOSComputerUseClient

client = MacOSComputerUseClient(
    allowed_apps=("TextEdit",),
    allow_coordinate_click=False,
)

readiness = client.readiness()
result = client.open_app("TextEdit")
snapshot = client.observe(target_app="TextEdit")
typed = client.type_text("hello", target_app="TextEdit")
```

Core operations:

| Operation | Package Responsibility | High-Risk Behavior |
|---|---|---|
| `readiness` | Report platform, permission, backend, and setup state. | No OS mutation. |
| `observe` | Return bounded structured UI summary. | Hide sensitive fields and avoid screenshots by default. |
| `open_app` | Open allowlisted app and verify visibility/focus. | Block non-allowlisted apps. |
| `click` | Click resolved low-risk semantic target. | Block send/pay/delete/submit/system actions without caller authorization. |
| `type_text` | Type bounded text into focused editable target. | Do not press Enter or send. |
| `wait` | Wait for app/window/target readiness. | No OS mutation. |

Result statuses:

| Status | Meaning |
|---|---|
| `ok` | Operation completed. |
| `blocked` | Operation was refused by policy, permission, or risk gate. |
| `needs_user` | Manual setup, login, disambiguation, or focus is needed. |
| `not_available` | Platform, permission, or backend is unavailable. |
| `failed` | Operation failed unexpectedly with sanitized diagnostics. |

## 5. Packaging Layout

Recommended monorepo layout before extraction:

```text
packages/macos-computer-use/
  pyproject.toml
  README.md
  LICENSE
  src/macos_computer_use/
    __init__.py
    client.py
    models.py
    readiness.py
    accessibility.py
    app_control.py
    target_resolution.py
    input_control.py
    policy.py
    errors.py
  tests/
  examples/
    textedit_smoke.py
```

The package should be PEP 517/518 compatible and build a wheel plus sdist. It
should not depend on Taskweavn.

Recommended dependency policy:

- required runtime dependencies: minimal;
- optional macOS bridge dependencies grouped behind extras if needed;
- dev dependencies separated under `dev`;
- no OpenAI, Anthropic, LangChain, UI-TARS, Electron, React, or Taskweavn
  dependency.

Example dependency shape:

```toml
[project]
name = "macos-computer-use"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy"]
```

Exact OS bridge dependencies should be selected during implementation after the
minimal Accessibility strategy is validated.

## 6. External Publishing Strategy

Preferred public release path:

1. Build locally from a clean checkout.
2. Publish prerelease artifacts to TestPyPI.
3. Validate installation in a clean virtual environment on macOS.
4. Tag a GitHub release.
5. Publish wheel and sdist to PyPI through trusted publishing or a repository
   approved upload client.
6. Attach release notes, permission setup instructions, and manual smoke
   checklist.

Versioning:

- start at `0.1.0`;
- use SemVer;
- keep `0.x` while the API is experimental;
- avoid breaking API changes within a pinned minor range after Plato consumes
  it.

License:

- choose before public publish;
- Apache-2.0 is preferred if a patent grant is useful;
- MIT is acceptable if maximum adoption simplicity is preferred.

Publishing acceptance:

- wheel installs on a clean macOS Python environment;
- `python -c "import macos_computer_use"` succeeds;
- `readiness()` returns a structured result without extra setup;
- package tests pass without GUI permissions by using fake probes;
- README explains macOS Accessibility setup and safety boundaries.

## 7. Plato Integration Strategy

Plato should consume the package through dependency configuration, for example:

```toml
dependencies = [
  "macos-computer-use>=0.1,<0.2; sys_platform == 'darwin'",
]
```

Plato-owned adapter responsibilities:

```text
Task API / AgentLoop
  -> Plato computer_use tool facade
  -> PlatoMacOSComputerUseAdapter
  -> macos_computer_use.MacOSComputerUseClient
  -> package result
  -> Plato ComputerUseObservation / EventStream / confirmation handoff
```

The Plato adapter owns:

- mapping package operations to the existing `ComputerUseAction` contract;
- mapping package results to `ComputerUseObservation`;
- calling Plato `request_confirmation` when package risk metadata requires it;
- verifying durable confirmation authorization before retrying high-risk
  actions;
- storing observations, evidence refs, and audit metadata;
- feature flag / runtime config selection.

The package owns:

- macOS permission and readiness probes;
- low-level OS operation safety;
- target resolution;
- sanitized result models.

## 8. Implementation Phases

### Pkg-0. Contract Finalization

- Freeze public package boundary.
- Add package technical design.
- Confirm license and package name.
- Confirm whether package lives initially in this monorepo or a separate repo.

### Pkg-1. Package Skeleton

- Add package directory, `pyproject.toml`, README, license, and base models.
- Add fake probe/client tests.
- No real OS mutation.

### Pkg-2. Readiness And Observe

- Implement platform/readiness probes.
- Implement Accessibility-first observation seam.
- Add manual TextEdit readiness/observe smoke.

### Pkg-3. Safe App/Input Operations

- Implement allowlisted `open_app`.
- Implement focused editable `type_text`.
- Implement target-resolved click for low-risk targets.
- Keep coordinate fallback disabled by default.

### Pkg-4. Public Package Release

- Build wheel/sdist.
- Publish to TestPyPI.
- Validate clean install.
- Publish initial PyPI prerelease or public `0.1.0`.

### Pkg-5. Plato Adapter

- Add Plato dependency on released package.
- Add adapter mapping package result to Plato `ComputerUseObservation`.
- Keep disabled/scripted backend as fallback.
- Add sidecar and AgentLoop tests.

### Pkg-6. Vertical Proof

- Use the package through Plato for a safe local TextEdit task.
- Only after that, design WeChat/contact/message-specific adapters.

## 9. Acceptance Criteria

This planning track is ready for implementation when:

1. package boundary is documented;
2. publish target and versioning policy are documented;
3. package has no dependency on Plato, TaskBus, Session, AgentLoop, or LLMs;
4. Plato adapter boundary is documented;
5. macOS backend docs reference the package as the implementation source;
6. gaps registry distinguishes package work from Plato adapter work.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Package grows into an Agent framework. | Keep LLM, planner, TaskBus, and UI out of package scope. |
| Plato couples to private package internals. | Consume only public API through a versioned dependency. |
| macOS permissions differ across machines. | Treat readiness as first-class result and document setup. |
| Public package reputation risk from unsafe automation. | Default to disabled/high-risk blocked behavior and explicit allowlists. |
| API churn breaks Plato. | Use `0.x` versioning and pin Plato to a compatible minor range. |
| External users need different UI/confirmation systems. | Return structured risk metadata; do not embed confirmation UI. |

## 11. Open Questions

1. Should the initial package be developed inside this monorepo and extracted
   later, or created in a new public repo from the start?
2. Should the public package name include `plato`, or stay neutral as
   `macos-computer-use`?
3. Which license should be used for public release?
4. Which macOS bridge dependency strategy is acceptable for `0.1.0`?
5. Should screenshot support be a separate optional package later?
