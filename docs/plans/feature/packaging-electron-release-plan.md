# Feature Plan: Packaging And Electron Release Readiness

> Status: accepted for Product 1.0 local unsigned RC
> Last Updated: 2026-06-07
> Gap: [Packaging and distribution](../../gaps/README.md)
> Architecture: [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Configurable Logging System](../../architecture/configurable-logging-system.md)
> Product: [Plato UI API Contract](../../product/plato-ui-api-contract.md), [Frontend QA Runbook](../../product/plato-1-0-frontend-qa-runbook.md), [Frontend QA Notes - 2026-06-06](../../product/plato-1-0-frontend-qa-notes-2026-06-06.md)
> Related Plans: [Local Sidecar API Shell](local-sidecar-api-shell.md), [Settings first-run frontend completion](settings-first-run-frontend-completion.md), [Diagnostic bundle export](diagnostic-bundle-export.md), [Result exposure surface](result-exposure-surface.md), [Product error handling](product-error-handling.md)
> Release Record: Product 1.0 local unsigned RC accepted on 2026-06-07; signed distribution deferred until Apple Developer credentials are available.

---

## 1. Problem / Gap

Product 1.0 now has a repeatable browser-side integration path:

- the local Python sidecar exposes the UI HTTP/SSE contract;
- `npm run test:e2e:sidecar` covers deterministic sidecar fixtures;
- `npm run dev:sidecar:first-run` and `npm run dev:sidecar:configured`
  remove manual Vite environment copying for browser development;
- Main Page, Settings first-run, Audit evidence, Diagnostic Bundle export, and
  Product error recovery labels have normal browser smoke coverage.

The Product 1.0 local unsigned RC packaging path is now accepted. E1/E2 provide
the Electron dev shell, main-owned Python sidecar lifecycle, startup diagnostics
foundation, and preload runtime injection. E5 adds deterministic configured
Electron smoke through `npm run electron:smoke`, covering Main Page, Audit
evidence, Diagnostic Bundle export, and command-failure recovery labels. The
follow-up `npm run electron:smoke:first-run` covers Settings first-run setup,
save/recheck, secret redaction, and transition into Main Page. E6 adds an
unsigned package directory and `npm run electron:smoke:packaged`, reusing the
configured and first-run acceptance paths outside Vite/dev-shell mode. Startup
diagnostics hardening validates startup failure without a seeded external
sidecar. The release-local launcher encapsulates Python runtime details behind
Electron main lifecycle ownership. E14 adds the unsigned DMG and mounted
installer smoke, and manual Finder launch reaches Main Page.

The remaining release path is signed/notarized distribution, deferred until
Apple Developer credentials are available.

---

## 2. Current Facts

| Area | Current state |
|---|---|
| Frontend runtime | Vite/React app supports HTTP mode through `VITE_PLATO_API_MODE=http`, `VITE_PLATO_API_BASE_URL`, and optional `VITE_PLATO_SESSION_ID`. |
| Sidecar runtime | `uv run taskweavn plato-sidecar --workspace <path> --port 0` can start the local Python sidecar on a free loopback port. |
| Combined browser dev | `uv run taskweavn plato-dev --workspace ./plato-workspace` starts sidecar plus Vite for developer use. |
| Fixture runner | `tests/fixtures/sidecar_smoke.py --keep-alive --ready-file <json>` emits a machine-readable descriptor for frontend E2E. |
| Product QA | Formal sidecar E2E and normal browser smoke have passed for the covered Product 1.0 paths. |
| Packaging | Accepted for Product 1.0 local unsigned RC. `npm run electron:dev` starts Vite, launches Electron, lets Electron main own the Python sidecar, injects HTTP runtime config through preload, and shows startup diagnostics on sidecar failure. `npm run electron:smoke` starts a seeded sidecar fixture, launches Electron in smoke mode, and validates the configured Product 1.0 Main Page/Audit/Diagnostics/recovery path. `npm run electron:smoke:first-run` validates Settings first-run save/recheck, secret redaction, and Main Page entry in the Electron dev shell. `npm run electron:package:dir` builds an unsigned local app directory, and `npm run electron:smoke:packaged` validates configured, first-run, and startup-diagnostics paths against the packaged app without Vite. Signed runtime planning selects a release-local launcher boundary. `npm run electron:package:launcher-dir` builds a launcher-backed package with bundled Python behind the launcher: `python-base` owns the interpreter/stdlib/native library closure, `python-env` carries vendored site-packages, and `python-src` carries Product 1.0 sidecar source/fixtures. `npm run electron:smoke:launcher` validates configured, first-run, and startup-diagnostics paths through that package-local bundled runtime without repo `uv`, repo `src/tests`, the developer `.venv`, external Python symlinks, or external `pyvenv.cfg`. `npm run electron:check:release-assets` returns `ok=true` for the bundled runtime. `npm run electron:package:installer` creates the local unsigned DMG installer candidate from the release-asset-checked launcher package. `npm run electron:smoke:installer` mounts the DMG read-only and validates configured/default-workspace, first-run, and startup-diagnostics paths through the mounted launcher-backed bundled runtime. Manual Finder launch from the unsigned DMG reached Main Page. Developer ID signing identity/entitlements, notarization credential validation, Gatekeeper assessment, and signed installer acceptance are deferred until Apple Developer credentials are available. |

---

## 3. Product Goal

Product 1.0 release readiness is complete when a local desktop user can open
Plato as a desktop app and get the same Product 1.0 loop validated in browser
smoke:

1. Electron starts a renderer shell.
2. Electron main process starts and owns the Python sidecar.
3. The app shows startup diagnostics if the sidecar cannot become ready.
4. The renderer receives safe runtime config without manual environment
   variables.
5. Settings first-run, Main Page, Audit evidence, Diagnostic Bundle export, and
   Product error guidance work through the desktop shell.
6. QA can run deterministic smoke commands for both configured and first-run
   desktop paths.

### 3.1 Product 1.0 Local RC Closure

Accepted on 2026-06-07 for local unsigned RC:

- `frontend/dist-electron-installer/Plato-0.1.0-macos-arm64.dmg` is the local
  unsigned release-candidate artifact;
- SHA256:
  `0eeb265a5f6ccb17958eb8a6dbb97aa50afaa842b706e946e14df298719877b2`;
- `hdiutil verify` passed;
- `npm run electron:check:release-assets -- --json` returned `ok=true` with
  `runtimeKind=bundled-python` and `externalSymlinks=0`;
- `npm run electron:smoke:installer -- --skip-package` passed the mounted DMG
  configured packaged-default-workspace, first-run, and startup-diagnostics
  paths;
- manual Finder launch from the unsigned DMG reached Main Page.

This closes Product 1.0 local unsigned RC readiness. Signed distribution,
notarization, Gatekeeper assessment, and signed installer acceptance are
deferred until Apple Developer credentials are available.

---

## 4. Non-Goals

- Do not implement deterministic Electron acceptance smoke in E1/E2.
- Do not choose or build signed installers in the first implementation slice.
- Do not add remote server deployment or multi-user authentication.
- Do not replace the local Python sidecar with a Node backend.
- Do not implement full centralized runtime configuration.
- Do not expose raw exception, prompt, provider payload, log payload, SQLite
  payload, workspace root, or secret values to the renderer.
- Do not run real provider network validation in deterministic smoke commands.
- Do not evaluate or implement Tauri for Product 1.0 release readiness.

---

## 5. Release Architecture

### 5.1 Desktop Shell Ownership

Product 1.0 release readiness will use Electron as the desktop shell.

Rationale:

- the frontend package is already a Node/Vite project;
- the Browser/Electron smoke gap is release-readiness work, not a broader
  desktop framework research project;
- Electron main process can own a child Python sidecar, inject renderer
  runtime config, and drive smoke commands with the same Node test harness
  already used by sidecar E2E.

Expected implementation layout:

```text
frontend/
  electron/
    main.ts
    preload.ts
    startupDiagnostics.ts
    sidecarProcess.ts
  scripts/
    run-electron-smoke.mjs
```

The exact file names can change during implementation, but responsibilities
must stay separated:

- `main`: app lifecycle, window creation, sidecar ownership, startup state;
- `preload`: safe renderer bridge only;
- `sidecarProcess`: Python command assembly, ready detection, termination;
- `startupDiagnostics`: redacted startup manifest and user-facing failure
  facts;
- smoke runner: deterministic acceptance commands.

### 5.2 Python Sidecar Ownership

In packaged/default desktop mode, Electron main process owns the Python
sidecar. The renderer must not start, kill, or inspect the Python process.

Required lifecycle:

```text
Electron app starts
  -> resolve workspace root
  -> choose a free loopback sidecar port
  -> create a per-process sidecar token when auth is enabled
  -> spawn Python sidecar
  -> wait for a machine-readable ready descriptor or /api/v1/health
  -> create BrowserWindow
  -> inject safe renderer runtime config through preload
  -> terminate sidecar on app quit
```

Implementation should prefer a machine-readable ready file/stdout protocol over
parsing human-oriented CLI logs. If the production sidecar CLI cannot emit a
ready descriptor yet, add a small backend/CLI slice before Electron smoke.

Accepted sidecar command shape for the current repo-managed unsigned package
smoke:

```text
uv run taskweavn plato-sidecar \
  --workspace <workspace> \
  --host 127.0.0.1 \
  --port 0
```

Signed packaged builds use a release-local launcher boundary. Product 1.0 now
selects bundled Python behind that launcher; frozen sidecar packaging is
deferred. The sidecar remains Python-owned and exposes only the existing local
UI contract to the renderer.

#### Product 1.0 Packaged Runtime Ownership Decision

Decision recorded on 2026-06-07:

- Electron main owns Python sidecar startup, health polling, startup
  diagnostics, and process shutdown for Product 1.0 desktop mode.
- The unsigned local app-directory package used for Product 1.0 release smoke
  depends on the repository-managed Python runtime and invokes
  `uv run taskweavn plato-sidecar` from `PLATO_ELECTRON_REPO_ROOT`.
- The renderer never starts, stops, or inspects the Python process. It only
  receives redacted runtime config through preload after the sidecar is ready.
- Seeded external sidecars are allowed only for deterministic configured and
  first-run acceptance paths. Packaged startup diagnostics must be validated
  without `PLATO_ELECTRON_SIDECAR_BASE_URL`.
- Replacing the repo-managed runtime path in signed distribution is deferred to
  the signing/installer release slice. That later slice must preserve Electron
  main ownership and the same redaction rules.

#### Signed Installer Runtime Decision

Decision recorded on 2026-06-07:

- Product 1.0 signed distribution should use a release-local sidecar launcher
  boundary instead of letting Electron main directly know Python, venv, or
  dependency layout details.
- Electron main remains responsible for app lifecycle, child-process lifecycle,
  health polling, timeout handling, startup diagnostics, runtime config
  injection, and shutdown.
- The launcher is responsible for resolving packaged Python runtime details,
  selecting the concrete sidecar executable strategy, preparing the sidecar
  process environment, forwarding stdout/stderr, forwarding termination signals,
  and exiting with the sidecar result.
- In packaged builds, Electron main invokes the launcher through the packaged
  Electron binary with `ELECTRON_RUN_AS_NODE=1`; Finder/manual startup must not
  depend on a developer shell `node` executable being present on `PATH`.
- In packaged builds without an explicit `PLATO_ELECTRON_WORKSPACE`, Electron
  main resolves the sidecar workspace under the app `userData` directory
  (`Application Support/Plato/workspace` on macOS). Finder/manual startup must
  never write workspace data under the read-only app bundle or mounted DMG.
- The renderer remains unaware of launcher or Python details. It only receives
  the same redacted HTTP runtime config through preload after sidecar readiness.
- Bundled Python remains an implementation detail behind the launcher, not an
  Electron main contract. Future frozen sidecar work may replace the launcher
  internals without changing renderer or Electron main semantics.

#### Product 1.0 Final Runtime Decision

Decision recorded on 2026-06-07:

- Product 1.0 signed distribution should ship bundled Python behind the
  release-local launcher.
- The launcher remains the only Electron-main-facing runtime boundary. Electron
  main must not learn Python executable, stdlib, venv, wheel, site-packages, or
  source layout details.
- Frozen sidecar packaging is deferred. It remains a future optimization for
  bundle size and distribution ergonomics, not the Product 1.0 path.
- The bundled runtime should package a Python executable/runtime, Python
  dependencies, Taskweavn sidecar code, and fixture/smoke support needed by
  deterministic release smoke.
- The bundled runtime must not depend on repo `uv`, repo `src/tests`, editable
  `.pth` files, developer `.venv`, or `PLATO_ELECTRON_REPO_ROOT`.
- Final runtime packaging may be implemented as a cleaned bundled venv, a wheel
  install into a relocatable environment, or another Python runtime layout, but
  the accepted product strategy is bundled Python behind launcher rather than a
  frozen sidecar binary.

Required signed package runtime layout:

```text
Plato.app/
  Contents/
    Resources/
      app/
        dist/                  # production renderer
        electron/              # Electron main/preload/startup diagnostics
        sidecar/
          plato-sidecar-launcher
          runtime/
            launcher-runtime.json
            python-env/         # bundled Python runtime/dependencies
            python-src/         # Taskweavn sidecar code or installed wheel source
```

Launcher input contract:

- `--workspace <path>`;
- `--host 127.0.0.1`;
- `--port <port>`;
- optional `--ready-file <path>` once the ready descriptor protocol is accepted;
- environment keys from Electron main only for safe runtime configuration,
  never raw user secrets unless an accepted auth transport requires a private
  token.

Launcher output contract:

- preserves sidecar stdout/stderr streams so Electron startup diagnostics can
  apply existing redaction;
- exits non-zero when runtime resolution or sidecar startup fails;
- forwards termination to the underlying sidecar process;
- does not print raw workspace roots, provider payloads, prompts, SQLite rows,
  or secret values.

Launcher diagnostics categories:

| Category | Meaning | Startup diagnostics behavior |
|---|---|---|
| `launcher_missing` | Packaged launcher is absent or not executable. | Show `sidecar_failed`, launcher category, app/runtime alias, and startup id. |
| `runtime_missing` | Launcher exists but packaged Python runtime cannot be resolved. | Show `sidecar_failed`, runtime category, redacted launcher stderr. |
| `runtime_failed` | Runtime starts but exits before health readiness. | Show exit code/signal and redacted recent output. |
| `health_timeout` | Runtime stays alive but sidecar health does not become ready. | Show timeout, health URL host/port, and redacted output. |

Signed runtime smoke direction:

- keep current `npm run electron:smoke:packaged` as the repo-managed unsigned
  package-dir smoke;
- use the launcher-backed package smoke that does not require
  `PLATO_ELECTRON_REPO_ROOT`, Electron-main `uv`, or a seeded external sidecar
  for startup;
- reuse the configured, first-run, and startup-diagnostics acceptance paths
  after the launcher runtime is available;
- keep real provider network validation out of deterministic smoke.

### 5.3 Asset Layout Checker Contract

The release asset checker is an implemented static command that runs before
signing and notarization. It validates that the app directory is safe to sign and that
runtime assets are package-local.

Implemented command:

```text
cd frontend && npm run electron:check:release-assets -- --package-dir ./dist-electron-launcher
```

Required inputs:

- an app directory produced by `electron:package:launcher-dir` or its future
  signed-runtime successor;
- `package-manifest.json`;
- `sidecar/runtime/launcher-runtime.json`;
- bundled Python runtime files under `Contents/Resources/app/sidecar/runtime/`.

Required checks:

- launcher runtime manifest uses package-local relative paths;
- no repo path, user home path, workspace path, `.venv`, `uv`, editable `.pth`,
  `.egg-link`, provider payload, prompt, SQLite payload, log payload, or secret
  string appears in runtime manifests or launcher config;
- every symlink under the app bundle resolves inside `Plato.app`;
- every executable script, Mach-O binary, `.dylib`, framework, and helper is
  discoverable in the executable/native inventory, with executable permissions
  checked for required entrypoints;
- runtime writes are configured for user workspace or application support
  paths, not `Contents/Resources`;
- launchers and nested executable code are discoverable for inside-out signing;
- the checker emits a machine-readable summary for CI and a concise failure
  reason that does not reveal raw local paths beyond redacted aliases.

Non-goals:

- it does not call real LLM providers;
- it does not notarize;
- it does not mutate the app bundle except in a separately accepted fix mode.

### 5.4 Startup Diagnostics

Desktop startup must have explicit states instead of a blank app window:

| State | Meaning | User-visible result |
|---|---|---|
| `starting_shell` | Electron app booted. | Minimal loading surface. |
| `starting_sidecar` | Python sidecar process spawned. | Loading with local setup label. |
| `waiting_for_health` | Sidecar process is alive but API is not ready. | Loading with timeout budget. |
| `injecting_runtime` | Renderer config is being prepared. | Loading; no secret display. |
| `first_run_blocked` | Sidecar is ready but Settings readiness is not. | Existing first-run Settings path. |
| `ready` | Sidecar and renderer are connected. | Main Page. |
| `sidecar_failed` | Python process failed, timed out, or exited early. | Startup diagnostics view. |
| `renderer_config_failed` | Renderer did not receive valid runtime config. | Startup diagnostics view. |

Startup diagnostics may include:

- app version;
- Electron version;
- sidecar command category, not raw command with secrets;
- sidecar exit code/signal;
- redacted recent sidecar stderr/stdout lines;
- health URL host/port only;
- startup timeout;
- workspace alias such as `workspace://current`, not the raw filesystem root;
- Diagnostic Bundle export availability when the sidecar reached a state that
  can produce one.

Startup diagnostics must not include:

- API keys or token values;
- raw prompt/provider payloads;
- raw SQLite rows;
- full workspace filesystem paths;
- unredacted log payloads.

### 5.4 Renderer Runtime Injection

Packaged renderer runtime must not depend on build-time `VITE_*` values.

Electron preload should expose a minimal bridge, for example:

```ts
window.platoRuntimeConfig = {
  apiMode: "http",
  apiBaseUrl: "http://127.0.0.1:<port>",
  sessionId: "<optional-initial-session-id>",
  appVersion: "<version>",
  startupId: "<opaque-id>"
};
```

If sidecar auth is enabled, the token must be handled as a private transport
credential. It may be passed to the HTTP client through the preload bridge, but
it must not be rendered, logged, stored in frontend diagnostics, or exposed in
DOM-visible text.

Frontend API client work must stay small:

- preserve the current browser `VITE_*` fallback for development;
- add a runtime-config resolver that prefers Electron preload config when
  available;
- keep `createHttpPlatoApi` as the transport client;
- add token/header support only if the sidecar auth guard requires it.

### 5.5 Security And Redaction

Release shell rules:

- bind the sidecar to loopback only;
- never listen on a public interface by default;
- use a random per-process token when the sidecar auth guard is enabled;
- restrict renderer origins to the packaged app and local dev hosts;
- redact sidecar logs before showing startup diagnostics;
- include startup facts in Diagnostic Bundle only after applying the existing
  diagnostics redaction policy;
- never expose stored secret values in Settings, logs, diagnostics, or startup
  views.

---

## 6. Smoke Command Contract

These commands are the required executable entries for the full release path.
`electron:dev` is available after E1/E2, configured `electron:smoke` is
available after E5, first-run `electron:smoke:first-run` is available after
the E5 follow-up, and package commands are available after E6.

| Command | Purpose | Expected result |
|---|---|---|
| `cd frontend && npm run electron:dev` | Start Electron with dev renderer and main-owned sidecar. | Available after E1/E2. Desktop window opens with HTTP runtime injected by preload. |
| `cd frontend && npm run electron:smoke` | Deterministic configured Product 1.0 desktop smoke. | Available after E5. Main Page -> Audit -> record/detail/evidence, diagnostics export, and command-failure recovery labels pass against seeded sidecar data. |
| `cd frontend && npm run electron:smoke:first-run` | Deterministic unconfigured first-run desktop smoke. | Available after E5 follow-up. Settings modal opens, save/recheck reaches Main Page, and secret values are not exposed in rendered text or retained controls. |
| `cd frontend && npm run electron:package:dir` | Build an unsigned local app directory for release-readiness smoke. | Available after E6. Produces `frontend/dist-electron/Plato.app` on macOS using the current production renderer build. |
| `cd frontend && npm run electron:smoke:packaged` | Smoke the unsigned packaged app directory. | Available after E6 plus startup-diagnostics hardening. Rebuilds the local app directory and runs configured, first-run, and startup-diagnostics smoke paths outside Vite/dev-server mode. |
| `cd frontend && npm run electron:smoke -- --packaged --startup-diagnostics` | Targeted packaged startup-failure diagnostics smoke. | Available after startup-diagnostics hardening. Launches the packaged app without a seeded external sidecar, forces a short main-owned sidecar startup timeout, and verifies redacted diagnostics. |
| `cd frontend && npm run electron:package:launcher-dir` | Launcher-backed package directory. | Available after E13. Builds an unsigned app directory with `sidecar/plato-sidecar-launcher.mjs`, `sidecar/runtime/launcher-runtime.json`, package-local `python-base`, `python-env`, and `python-src` assets. |
| `cd frontend && npm run electron:smoke:launcher` | Launcher-backed packaged runtime smoke. | Available after E13. Runs configured, first-run, and startup-diagnostics smoke through the packaged launcher without `PLATO_ELECTRON_REPO_ROOT`, Electron-main `uv` startup, repo `src/tests`, the developer `.venv`, external Python symlinks, or external `pyvenv.cfg`. |
| `cd frontend && npm run electron:check:release-assets` | Static release asset layout checker. | Available after E12 and passing after E13. Validates package-local runtime manifest, symlink containment, executable/native-code inventory, write-location boundaries, and signing/notarization-sensitive bundle layout before signing. Expected bundled runtime result is `ok=true`, `runtime=bundled-python`, and `externalSymlinks=0`. |
| `cd frontend && npm run electron:package:installer` | Build a local DMG installer candidate. | Available after E14. Rebuilds the launcher package, runs `electron:check:release-assets`, stages `Plato.app`, creates `dist-electron-installer/Plato-<version>-macos-<arch>.dmg`, and writes `installer-manifest.json`. Default output is unsigned/unnotarized. `--sign` requires `PLATO_ELECTRON_CODESIGN_IDENTITY` or `CSC_NAME`; `--notarize` additionally requires `PLATO_ELECTRON_NOTARY_KEYCHAIN_PROFILE` or Apple ID credentials. |
| `cd frontend && npm run electron:smoke:installer` | Mounted installer acceptance smoke. | Available after E14. Mounts the DMG read-only, normalizes package manifest paths to the mounted volume, then runs configured, first-run, and startup-diagnostics acceptance paths through the mounted launcher-backed bundled Python app with a Finder-like PATH. The configured path intentionally omits `PLATO_ELECTRON_WORKSPACE` and uses a temp `userData` root so external developer Node dependencies and read-only DMG workspace bugs are not masked. |

The deterministic smoke commands must use sidecar fixtures or seeded local
workspace data. They must not require real provider credentials.

---

## 7. Implementation Slices

### E1 - Electron Scaffold And Scripts

Status: implemented on 2026-06-07.

Add Electron dependencies, main/preload build setup, and package scripts.

Acceptance:

- `npm run electron:dev` opens a desktop window;
- the renderer can load from Vite in dev mode;
- no Python sidecar ownership is required yet;
- docs identify remaining blocked smoke paths.

### E2 - Main-Owned Sidecar Lifecycle

Status: implemented on 2026-06-07.

Implement Electron main process ownership for the Python sidecar.

Acceptance:

- Electron chooses a loopback port and starts the sidecar;
- a ready descriptor or health polling produces `apiBaseUrl`;
- sidecar exits on app quit;
- early sidecar failure renders startup diagnostics instead of a blank window.

### E3 - Renderer Runtime Config Injection

Status: foundation partially implemented on 2026-06-07 for dev Electron HTTP
runtime injection. Token handling and packaged-runtime hardening remain open.

Bridge safe runtime config from Electron main/preload to the frontend API
client.

Acceptance:

- packaged/dev Electron renderer no longer needs manual `VITE_PLATO_API_*`
  values;
- browser development still supports the existing Vite env path;
- token handling is redacted when enabled.

### E4 - Startup Diagnostics And Diagnostic Bundle Linkage

Status: startup diagnostics surface and packaged startup-failure smoke
implemented on 2026-06-07. Diagnostic Bundle linkage for startup facts remains
open until safe partial-sidecar export semantics are accepted.

Add startup diagnostics state and redacted startup manifest.

Acceptance:

- sidecar timeout/early-exit shows a user-readable diagnostics surface;
- redaction rules match Product 1.0 diagnostics policy;
- Diagnostic Bundle includes startup facts only when safe and available.

### E5 - Electron Acceptance Smoke

Status: implemented for configured Product 1.0 smoke and first-run Settings
smoke on 2026-06-07. The implemented commands are `npm run electron:smoke`,
covering Main Page, Audit evidence, Diagnostic Bundle export, and
command-failure recovery labels, and `npm run electron:smoke:first-run`,
covering Settings first-run setup, save/recheck, secret redaction, and Main
Page entry.

Promote browser Product 1.0 acceptance coverage to Electron smoke.

Acceptance:

- `npm run electron:smoke` validates configured Main Page, Audit evidence,
  Diagnostic Bundle export, and command-failure recovery labels;
- `npm run electron:smoke:first-run` validates Settings first-run save/recheck;
- failures include enough startup/test evidence to debug without raw secrets.

### E6 - Packaged Directory Smoke

Status: implemented on 2026-06-07 for unsigned local app-directory smoke, then
hardened with packaged startup diagnostics coverage on 2026-06-07.

Build and smoke an unsigned packaged app directory.

Acceptance:

- `npm run electron:package:dir` produces a local launchable app directory;
- `npm run electron:smoke:packaged` runs without Vite;
- packaged startup diagnostics are validated without a seeded external sidecar;
- release notes clearly mark signing/notarization/installer as later work.

### E7 - Packaged Startup Diagnostics Hardening

Status: implemented on 2026-06-07.

Validate packaged startup failure without relying on the seeded sidecar fixture
used by configured and first-run acceptance smoke.

Acceptance:

- `npm run electron:smoke -- --packaged --startup-diagnostics` launches the
  packaged app without `PLATO_ELECTRON_SIDECAR_BASE_URL`;
- Electron main attempts to own Python sidecar startup through the repo-managed
  `uv run taskweavn plato-sidecar` path and hits a deterministic short timeout;
- the startup diagnostics view shows `sidecar_failed`, timeout evidence, and
  `workspace://current`;
- the smoke assertion fails if raw workspace/repository paths or secret-like
  values appear in the rendered diagnostics.

### E8 - Signed Runtime Launcher Plan

Status: accepted as the signed runtime direction on 2026-06-07.

Select and document the signed distribution runtime boundary.

Acceptance:

- Electron main remains the owner of process lifecycle, health polling,
  diagnostics, renderer runtime injection, and shutdown;
- a release-local launcher encapsulates Python runtime layout and concrete
  sidecar startup details;
- direct Python/venv bundling remains an implementation detail behind the
  launcher, not a renderer or Electron main contract;
- future smoke commands are defined for launcher-backed packaged runtime
  validation without repo-managed `uv`.

### E9 - Launcher-Backed Packaged Runtime Smoke

Status: implemented on 2026-06-07 for launcher-backed unsigned package smoke.

Implement the first launcher-backed package directory and deterministic smoke.

Acceptance:

- package output includes a launcher under `Contents/Resources/app/sidecar/`;
- Electron main can be pointed at the launcher without requiring
  `PLATO_ELECTRON_REPO_ROOT`;
- configured and first-run smoke pass against launcher-owned packaged runtime
  startup;
- startup diagnostics smoke validates launcher/runtime missing or timeout
  failures without exposing raw paths or secrets;
- the current repo-managed `electron:smoke:packaged` remains available for
  developer release-readiness regression until signed runtime smoke replaces it.

Implementation notes:

- `electron:package:launcher-dir` writes `dist-electron-launcher` with
  `sidecar/plato-sidecar-launcher.mjs` and
  `sidecar/runtime/launcher-runtime.json`.
- The E9 launcher smoke originally used a repo-local Python fixture runtime
  manifest for deterministic unsigned package validation. E10 replaces that
  manifest with a package-local self-contained Python environment candidate.
- `electron:smoke:launcher` seeds deterministic workspaces, then lets Electron
  main start the sidecar through the package-local launcher. The renderer never
  receives launcher or Python details.

### E10 - Self-Contained Runtime Candidate

Status: implemented on 2026-06-07 as an unsigned package-local Python
environment candidate.

Replace the E9 repo-local fixture runtime manifest with package-local runtime
assets.

Acceptance:

- `electron:package:launcher-dir` writes a launcher runtime manifest with
  `runtimeKind: self-contained-python-env-candidate`;
- runtime manifest paths are relative to `sidecar/runtime/` and point to
  package-local `python-env` and `python-src` assets;
- launcher smoke workspace seeding and Electron main-owned launcher startup do
  not use repo `uv`, `PLATO_ELECTRON_REPO_ROOT`, repo `src/tests`, or the
  developer `.venv`;
- configured, first-run, and startup-diagnostics launcher smoke use the same
  package-local runtime boundary;
- final signing/notarization/installer work remains separate.

Implementation notes:

- The candidate copies the local virtual environment into
  `sidecar/runtime/python-env`, removes the editable repo `.pth` entry, and
  copies Product 1.0 sidecar source plus smoke fixtures into
  `sidecar/runtime/python-src`.
- The manifest intentionally stores relative runtime asset paths, so the
  launcher resolves Python details from the package directory instead of the
  repository.
- This is a release candidate for the launcher/runtime boundary. It is not yet
  a compressed, signed, notarized installer and does not close the final
  bundled-Python binary strategy.

### E11 - Final Runtime Decision And Release Check Plan

Status: accepted as a planning slice on 2026-06-07.

Lock the Product 1.0 signed runtime strategy and define the next executable
release-readiness checks.

Acceptance:

- final Product 1.0 runtime strategy is bundled Python behind the
  release-local launcher;
- frozen sidecar is explicitly deferred as a future optimization;
- asset layout checker command contract is defined before signing work starts;
- installer smoke command contract covers configured, first-run, and startup
  diagnostics paths after install/mount;
- no implementation in this slice claims signing, notarization, or installer
  UX is complete.

E12 implementation contract:

- add `npm run electron:check:release-assets`;
- default checker input is `frontend/dist-electron-launcher`;
- checker output includes `ok`, package path, runtime kind, executable/native
  inventory, symlink count, redaction summary, and failure list;
- checker fails on external symlinks, repo/developer runtime references,
  editable installs, unsigned-code-discovery gaps, runtime write targets inside
  the app bundle, or raw secret/path payloads in manifests;
- installer smoke should reuse the same smoke runner assertions as
  `electron:smoke:launcher` after the distribution artifact is installed or
  mounted.

### E12 - Release Asset Layout Checker

Status: implemented on 2026-06-07.

Add the static pre-signing package layout gate.

Acceptance:

- `npm run electron:check:release-assets` reads `dist-electron-launcher` by
  default;
- the checker emits a machine-readable JSON summary with `ok`, package alias,
  runtime kind, executable/native inventory, symlink count, redaction summary,
  and failures;
- the checker fails on external symlinks, repo/developer runtime references,
  editable install metadata, runtime manifest path escapes, runtime write
  targets inside `Contents/Resources`, and raw secret-like values in release
  manifests/config;
- checker output redacts local package, repo, user-home, and external paths
  using aliases;
- no real provider validation, signing, notarization, or installer creation is
  performed.

Current result:

- the checker removes previous false positives from third-party package source
  examples by limiting secret scanning to release manifests/config;
- `electron:package:launcher-dir` removes editable `direct_url.json` metadata
  from copied dist-info directories;
- before E13, the checker correctly blocked the package candidate because
  `pyvenv.cfg` pointed to an external Python runtime and `python`, `python3`,
  and `python3.12` were symlinks outside `Plato.app`.

### E13 - Signable Bundled Python Runtime

Status: implemented on 2026-06-07.

Replace the external-linked virtual environment candidate with a signable
launcher-backed bundled Python runtime.

Acceptance:

- `electron:package:launcher-dir` writes `runtimeKind: bundled-python`;
- `sidecar/runtime/python-base/bin/python3` is a package-local executable;
- `python-base` owns the copied stdlib and Darwin native library dependency
  closure needed by Python extension modules;
- `python-env` carries vendored site-packages only and no longer copies
  `.venv/bin/python*` links or `.venv/pyvenv.cfg`;
- `launcher-runtime.json` keeps relative package-local paths only;
- the launcher and launcher smoke runner set `PYTHONDONTWRITEBYTECODE=1`, so
  smoke does not mutate the app bundle with `__pycache__` or `.pyc` files;
- `npm run electron:check:release-assets` returns `ok=true`,
  `runtime=bundled-python`, and `externalSymlinks=0`;
- `npm run electron:smoke:launcher -- --skip-package` passes configured,
  first-run, and startup-diagnostics paths against the bundled runtime.

Out of scope:

- production signing identity, hardened runtime entitlements, notarization,
  installer creation, and installed-app smoke.

### E14 - Local DMG Installer And Mounted Smoke

Status: accepted on 2026-06-07 as the Product 1.0 local unsigned RC.

Create an installer candidate and smoke it from a mounted distribution artifact
while preserving the launcher-owned bundled Python boundary.

Acceptance:

- `npm run electron:package:installer` rebuilds the launcher package and runs
  `npm run electron:check:release-assets` before creating a DMG;
- default installer output is an unsigned local DMG plus
  `dist-electron-installer/installer-manifest.json`;
- optional `--sign` uses `PLATO_ELECTRON_CODESIGN_IDENTITY` or `CSC_NAME` and
  fails clearly when no signing identity is provided;
- optional `--notarize` requires a signing identity and either
  `PLATO_ELECTRON_NOTARY_KEYCHAIN_PROFILE` or Apple ID, password, and Team ID
  environment variables;
- `npm run electron:smoke:installer -- --skip-package` mounts the DMG read-only,
  runs configured, first-run, and startup-diagnostics smoke against the mounted
  app, and detaches the DMG with retries;
- mounted smoke uses the same launcher-owned `runtimeKind: bundled-python`
  runtime and does not depend on repo `uv`, repo `src/tests`, the developer
  `.venv`, external Python symlinks, or external `pyvenv.cfg`.

Out of scope:

- proving a real Developer ID signing identity, hardened runtime entitlements,
  notarization submission, staple validation, Gatekeeper assessment, and a
  clean-machine signed installed-app run. Those require Apple credentials and a
  release machine profile and are deferred until those credentials are
  available.

---

## 8. Acceptance Matrix

| Path | Browser dev status | Electron dev target | Packaged target |
|---|---|---|---|
| Configured Main Page load | Passed | Passed by `electron:smoke` | Passed by `electron:smoke:packaged` |
| Settings first-run save/recheck | Passed | Passed by `electron:smoke:first-run` | Passed by `electron:smoke:packaged` |
| Main Page -> Audit -> record/detail/evidence | Passed | Passed by `electron:smoke` | Passed by `electron:smoke:packaged` |
| Diagnostic Bundle export | Passed | Passed by `electron:smoke` | Passed by `electron:smoke:packaged` |
| Product error recovery labels | Passed | Passed by `electron:smoke` | Passed by `electron:smoke:packaged` |
| Startup sidecar failure diagnostics | Not applicable | Startup diagnostics surface implemented | Passed by `electron:smoke:packaged` startup-diagnostics mode |
| Launcher-backed runtime startup | Not applicable | Not applicable | Passed by `electron:smoke:launcher` using package-local bundled Python behind the launcher |
| Release asset layout gate | Not applicable | Not applicable | Passed by `electron:check:release-assets` with `runtime=bundled-python`, `externalSymlinks=0`, and `ok=true` |
| Mounted DMG installer smoke | Not applicable | Not applicable | Passed by `electron:smoke:installer` for configured/default-workspace, first-run, and startup-diagnostics paths using mounted bundled Python app |
| Manual Finder launch from unsigned DMG | Not applicable | Not applicable | Passed for local unsigned RC; Main Page reached |
| Sidecar exits with app | Not applicable | process lifecycle assertion | process lifecycle assertion |
| No raw secret/path/log/provider payload exposure | Passed for browser-covered paths | smoke assertion | smoke assertion |

---

## 9. Risks And Assumptions

Risks:

- bundled Python source resolution may differ across developer machines until
  release assets are produced from a controlled build environment;
- packaging runtime assets can make signing/notarization sensitive to symlinks,
  binary permissions, and platform architecture;
- bundled Python can increase app size and signing time;
- native dependency closure may need tightening once the signing pipeline
  performs dylib load-command validation;
- the local DMG smoke validates mounted app behavior but does not prove
  Gatekeeper acceptance without a signed and notarized artifact;
- child-process cleanup can leave orphan sidecars if Electron exits abruptly;
- Vite dev renderer and packaged renderer can accidentally diverge in runtime
  config handling;
- sidecar token support may require a small API client update;
- macOS signing/notarization can introduce release work after local directory
  and local DMG smoke pass.

Assumptions:

- Product 1.0 release readiness now has local macOS package-directory and DMG
  smoke before signed installer distribution;
- Electron is the accepted Product 1.0 shell for this release-readiness path;
- unsigned Product 1.0 package-directory smoke can depend on the local repo
  runtime and `uv`; launcher-backed unsigned smoke now uses bundled Python
  behind the launcher;
- signed distribution should keep Electron main stable and put Python runtime
  details behind a release-local launcher;
- deterministic smoke should use fixture data and not call real LLM providers;
- actual Developer ID signing, notarization, Gatekeeper assessment, installer UX
  polish, and auto-update are later release slices.

---

## 10. Open Decisions For Implementation

Decision status for release-readiness implementation:

1. Electron packaging tool: `electron-builder`, `electron-forge`, or a smaller
   first local-directory packaging setup.
2. Python runtime strategy: closed for Product 1.0. Electron main owns
   lifecycle. Unsigned repo-managed package smoke uses
   `uv run taskweavn plato-sidecar`. Launcher-backed smoke uses package-local
   bundled Python behind the same release-local launcher. Frozen sidecar is
   deferred.
3. Ready descriptor protocol: fixture and smoke paths use ready files; the
   production `taskweavn plato-sidecar` ready descriptor remains a future
   hardening item.
4. App URL scheme: use a safe packaged renderer entry and documented allowed
   origins for sidecar requests.
5. Startup diagnostic persistence location and retention policy.

---

## 11. Deferred Signed Distribution Task Prompt

Run this only after Apple Developer credentials are available.

```text
Use the product-workflow-gate skill first.

Task:
Implement the credentialed signed/notarized distribution slice from
docs/plans/feature/packaging-electron-release-plan.md.

Scope:
- run the signing/notarization credentialed release slice for the local DMG
  installer foundation;
- provide `PLATO_ELECTRON_CODESIGN_IDENTITY` or `CSC_NAME`;
- provide either `PLATO_ELECTRON_NOTARY_KEYCHAIN_PROFILE` or
  `PLATO_ELECTRON_NOTARY_APPLE_ID`, `PLATO_ELECTRON_NOTARY_PASSWORD`, and
  `PLATO_ELECTRON_NOTARY_TEAM_ID`;
- run `npm run electron:package:installer -- --sign --notarize`;
- run `npm run electron:smoke:installer -- --skip-package`;
- preserve the launcher-owned bundled Python boundary and release asset checker;
- keep real provider validation out of deterministic smoke.

Do not call real LLM providers in smoke.
Do not expose raw exception, prompt, provider payload, log payload, SQLite
payload, workspace root, or secret values.

Output:
- files changed
- tests/checks run
- signing/notarization evidence
- installer smoke evidence
- bundled Python release asset checker preserved
- remaining release-readiness gaps
```
