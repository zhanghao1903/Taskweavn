# macOS Computer-Use Backend

> Status: in progress / helper provider client and prototype server implemented
>
> Last Updated: 2026-06-19
>
> Related:
> [Local Computer-Use Tool Foundation](local-computer-use-tool.md),
> [macOS Computer-Use Capability Package](macos-computer-use-package.md),
> [Technical Design](macos-computer-use-backend-technical-design.zh-CN.md),
> [Plato Computer Use Helper.app Technical Design](plato-computer-use-helper-app-technical-design.zh-CN.md),
> [Remote WeChat Message Task PRD](../../product/remote-wechat-message-task-prd.md),
> [Tool Capability Layer](../../architecture/tool-capability-layer.md),
> [Confirmation UI Spec](../../ux/confirmation-ui-spec.md),
> [Execution Plane Service And Task API](execution-plane-service-task-api.md)

---

## 1. Problem

The repository now has a safe `computer_use` foundation:

```text
Task API
  -> TaskBus
  -> AgentLoop
  -> computer_use tool
  -> disabled/scripted backend
  -> EventStream observation
```

This proves the service/tool/runtime seam, but it does not operate the real
desktop.

The next useful step is a minimal real macOS backend that can support local
operator experiments before remote ExecutionEnv, WeChat adapter, or network
distribution work.

## 2. Product Decision

Build the real macOS capability as an opt-in, permission-gated standalone
package first. The Taskweavn/Plato macOS backend is a consumer adapter over
that package, not the source of the OS automation implementation.

Working package name:

```text
macos-computer-use
```

Plato should later depend on the released package and map package results into
the existing `ComputerUseObservation`, confirmation, EventStream, and Audit
surfaces. Do not vendor the package source into Plato and do not import it
through repository-relative paths.

The backend must be useful enough to test real desktop automation primitives,
but conservative enough that it cannot silently send messages, click
irreversible controls, expose raw screen contents, or bypass user
authorization.

The first real backend should support only:

1. permission/readiness reporting;
2. `observe`;
3. `open_app`;
4. `click`;
5. `type_text`;
6. high-risk confirmation blocking and handoff.

Do not include WeChat-specific sending, contact resolution, network ExecutionEnv
routing, or screenshot evidence as part of this slice.

## 3. Scope

In scope:

- macOS platform readiness model;
- package public API / Plato adapter boundary;
- Accessibility permission readiness;
- optional Screen Recording readiness reporting, but no default screenshot use;
- allowlisted `open_app`;
- structure-first `observe`;
- target-resolved `click`;
- focused-editable `type_text`;
- high-risk operation classification;
- confirmation handoff for actions that can affect the external world;
- fake/probe-driven tests that do not require CI desktop permissions;
- manual local smoke checklist for macOS.

Out of scope:

- Windows backend;
- real WeChat Desktop adapter;
- sending a WeChat message;
- LAN remote ExecutionEnv registration / claim / lease;
- screenshot capture and redaction pipeline;
- password/credential entry;
- system dialog operation;
- production notarized permission onboarding;
- broad computer vision UI understanding.

Also out of scope for the package/backend split:

- LLM calls;
- AgentLoop implementation;
- TaskBus implementation;
- Plato UI or confirmation rendering inside the package.

## 4. Readiness Model

The backend must expose a readiness summary before it advertises real desktop
automation capability.

Readiness statuses:

| Status | Meaning | UI / Runtime Behavior |
|---|---|---|
| `ready` | Required backend and permissions are available for the enabled operation set. | `computer_use` can run low-risk allowed operations. |
| `unsupported_platform` | Host is not macOS. | Do not advertise macOS backend capability. |
| `backend_disabled` | Config disables real computer use. | Keep using disabled backend. |
| `missing_accessibility` | macOS Accessibility permission is missing. | Block `observe` tree reads, `click`, and `type_text`; show setup instructions. |
| `missing_screen_recording` | Screen Recording permission is missing. | Screenshot mode unavailable; structure-first observe can still work if Accessibility is ready. |
| `needs_manual_setup` | App is installed but not configured, logged in, or foreground-ready. | Return `needs_user` with operator action. |
| `error` | Probe failed unexpectedly. | Block real operations; preserve sanitized diagnostic details. |

Minimum permission matrix:

| Capability | Required Permission | Notes |
|---|---|---|
| `observe` via Accessibility tree | Accessibility | Preferred default observation mode. |
| `open_app` | None for basic app launch path, subject to allowlist | Use app name / bundle id allowlist. |
| `click` target | Accessibility | Prefer semantic target resolution and AXPress where possible. |
| `click` coordinate fallback | Accessibility | Disabled by default except debug/manual smoke. |
| `type_text` | Accessibility | Only into focused editable targets. |
| screenshot observe | Screen Recording | Deferred; never default in first real backend. |
| app-specific AppleScript | Automation / Apple Events entitlement | Deferred; avoid as the first implementation path. |

## 5. Operation Safety Boundaries

### 5.1 `observe`

Allowed:

- read frontmost application/window identity;
- read accessible UI roles, labels, values, and focused element summary;
- return bounded `text_extract`;
- return safe metadata such as app bundle id, window title, and element counts.

Blocked/deferred:

- raw screenshot by default;
- full chat transcript extraction by default;
- password field values;
- unrelated app contents when a target app is specified;
- storing raw UI tree without redaction.

### 5.2 `open_app`

Allowed:

- open a configured allowlisted app by canonical app name or bundle id;
- verify that the app becomes visible/frontmost within timeout;
- return `needs_user` if the app needs login, unlock, update, or manual setup.

Blocked:

- opening arbitrary URLs/files through `open_app`;
- opening apps outside the allowlist;
- using AppleScript to operate the app in this slice;
- repeated launch loops.

### 5.3 `click`

Allowed:

- click an allowlisted semantic target resolved from the latest observation;
- use AXPress if supported by the target element;
- use coordinate fallback only behind an explicit debug/manual-smoke flag.

Blocked:

- clicking by raw coordinates in normal runtime;
- clicking send/pay/delete/install/permission/system-dialog controls without a
  verified confirmation;
- clicking password/security prompts;
- clicking outside the target app/window;
- clicking stale targets from an old observation.

### 5.4 `type_text`

Allowed:

- type bounded text into the currently focused editable target;
- restore clipboard if a paste-based implementation is later used;
- return `needs_user` when no safe editable target is focused.

Blocked:

- typing into password/secure text fields;
- typing into unexpected apps;
- typing text longer than the configured limit;
- submitting/sending the text automatically;
- pressing Enter as part of `type_text`.

`type_text` may prepare a draft. It must not be treated as message delivery.
The send action requires a separate high-risk operation and confirmation.

## 6. High-Risk Confirmation Integration

The current runtime already has a `request_confirmation` tool and Main Page
confirmation UI.

For real computer-use, confirmation must protect known high-risk actions:

| Risk Class | Examples | Required Behavior |
|---|---|---|
| external message | send WeChat/email/chat message | Block until explicit confirmation. |
| irreversible UI action | delete, pay, submit, publish, install | Block until explicit confirmation. |
| sensitive visibility | expose private chat/screen contents | Block or return permission-limited evidence. |
| ambiguous target | multiple matching contacts/buttons | Stop and ask/confirm. |
| session approval request | "approve all similar actions" | Record only unless a later scoped approval policy exists. |

Minimal integration rule:

1. The backend policy classifies the requested action.
2. If high risk and no verified confirmation metadata is present, return a
   `blocked` `ComputerUseObservation`.
3. The observation must include safe metadata describing the required
   confirmation:

```json
{
  "confirmationRequired": true,
  "riskLabel": "external message",
  "recommendedConfirmation": {
    "title": "Confirm external message",
    "body": "Approve sending the drafted message to the selected contact.",
    "options": ["confirm", "reject"],
    "allowSessionApproval": true
  }
}
```

4. Agent guidance must instruct the Agent to call `request_confirmation` when
   it receives this blocked observation.
5. The actual high-risk operation must run only after the resolved confirmation
   can be verified against the action scope.

`approve_session` may be shown as a decision option only when the backend
supplies it. In this slice it remains a recorded response value and must not
silently bypass future confirmations. A true session-level approval policy
requires a later scoped approval design with TTL, task type, app, target, and
message-class constraints.

## 7. Implementation Slices

Implementation status as of 2026-06-26:

- Plato now supports `computer_use.backend=helper` as a runtime selection.
- The helper provider currently forwards generic `computer_use` operations to a
  configured local helper HTTP endpoint and maps helper readiness/errors back to
  `ComputerUseObservation`.
- A repo-local helper HTTP prototype server now exposes `/healthz`, `/v1/info`,
  `/v1/readiness`, and bounded generic operation endpoints over loopback.
- The actual `Plato Computer Use Helper.app` macOS wrapper, startup manifest
  writer, stable TCC identity, and release packaging are still pending.

### M0. Package Boundary And Skeleton

- Create the standalone package skeleton and public model/API contract.
- Keep package free of Taskweavn imports.
- Add package import/build tests.
- Keep Plato integration disabled until the package API is stable enough for
  adapter work.

### M1. Readiness Probe

- Add macOS readiness models and probe seam in the package.
- Detect platform and configured backend state.
- Probe Accessibility availability.
- Report Screen Recording as optional/deferred.
- Add tests with fake probes.

### M2. Real Backend Skeleton

- Add package client support for `observe`, `open_app`, and `wait` first.
- Add a Plato adapter behind explicit config.
- Keep Plato disabled backend as the default.
- Add no-GUI fake backend tests and one manual smoke checklist.

### M3. Safe Mutation Operations

- Add target-resolved `click`.
- Add focused editable `type_text`.
- Keep coordinate click disabled by default.
- Add policy-block tests for risky targets, password fields, stale targets,
  and missing readiness.

### M4. Confirmation Authorizer

- Add an explicit computer-use confirmation policy/authorizer.
- Support blocked observation -> `request_confirmation` handoff.
- Verify resolved confirmation metadata before high-risk operation execution.
- Keep session approval record-only unless scoped approval policy is designed.

### M5. Manual macOS Smoke

- Use a safe local app such as TextEdit.
- Verify readiness missing state.
- Verify `open_app`.
- Verify `observe`.
- Verify typing into a local unsaved document.
- Verify high-risk send-like action is blocked, not performed.

### M6. Public Package Release

- Build wheel and sdist.
- Publish to TestPyPI first.
- Validate clean macOS install.
- Publish `0.1.0` to PyPI only after README, permission setup, and smoke
  checklist are complete.

## 8. Acceptance Criteria

1. Real macOS backend is disabled by default.
2. A readiness API/model can distinguish unsupported platform, disabled backend,
   missing Accessibility, missing Screen Recording, ready, and error states.
3. `observe` does not require screenshots and does not expose raw unrelated
   screen contents.
4. `open_app` only operates allowlisted apps.
5. `click` and `type_text` are blocked without readiness.
6. `click` and `type_text` are blocked for high-risk targets without
   confirmation.
7. `type_text` does not submit/send.
8. No raw password fields, system dialogs, payment, delete, or send action is
   automated by default.
9. Tests use fake probes/backends and do not require CI macOS UI permissions.
10. Manual smoke can validate the real backend locally without WeChat.
11. Plato consumes macOS capability through a package dependency and adapter,
    not a direct source import.

## 9. Risks

| Risk | Mitigation |
|---|---|
| macOS permissions are user-granted and cannot be silently provisioned. | Treat readiness as product state and provide setup instructions. |
| Accessibility trees are incomplete for some apps. | Return `needs_user`; defer vision/screenshot fallback. |
| Coordinate clicks are brittle and dangerous. | Disable by default; prefer semantic target resolution. |
| Chat apps expose unrelated private content. | No raw screenshot/chat extraction by default. |
| Confirmation can be bypassed if only prompt-guided. | Add backend-side policy and confirmation metadata verification before high-risk operations. |
| Session approval can become unsafe. | Keep it record-only until scoped approval policy exists. |
| Package boundary leaks Plato concepts. | Keep TaskBus, Session, Confirmation UI, and Audit out of the package. |
| Public package API churn breaks Plato. | Use `0.x` versioning and pin Plato to a compatible minor range. |

## 10. References

- Apple Developer Documentation: [AXUIElement](https://developer.apple.com/documentation/applicationservices/axuielement)
- Apple Developer Documentation: [NSWorkspace](https://developer.apple.com/documentation/appkit/nsworkspace)
- Apple Developer Documentation: [ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit)
- Apple Developer Documentation: [Apple Events automation entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com_apple_security_automation_apple-events)
