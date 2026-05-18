# Packaging And Distribution Strategy

> Status: planned
> Type: release / distribution plan
> Last Updated: 2026-05-17
> Product Name: Plato
> Internal Project Name: TaskWeavn
> Target Implementation Session: independent packaging/release session

---

## 1. Purpose

Plato needs a distribution path that lets early users try the product without seeing source code, cloning the repository, installing Python/npm dependencies, or starting frontend/backend separately.

The first packaging baseline is:

```text
macOS Apple Silicon
local single-machine desktop app
Electron + React/TypeScript/Vite frontend
Python backend packaged as sidecar
PyInstaller for backend executable
signed + notarized dmg for any non-familiar users
manual update in v0
```

The product requirement is simple:

```text
User double-clicks Plato.app.
Plato starts UI and backend automatically.
User never manually starts frontend/backend separately.
```

---

## 2. Naming Decision

User-facing product name is **Plato**.

Internal project/repository name can remain **TaskWeavn**, but normal users should not see it.

Use Plato in all user-facing surfaces:

| Surface | Name |
|---|---|
| macOS app bundle | `Plato.app` |
| DMG | `Plato-mac-arm64-v0.1.0.dmg` |
| ZIP if used | `Plato-mac-arm64-v0.1.0.zip` |
| App data directory | `~/Library/Application Support/Plato/` |
| Default workspace directory | `~/Documents/PlatoWorkspaces/` |
| Window title | `Plato` |
| Settings / privacy / docs | `Plato` |
| Diagnostic bundle | `plato-diagnostics-YYYY-MM-DD.zip` |

---

## 3. Platform Scope

### 3.1 First Target

```text
macOS Apple Silicon only
```

Reasons:

- early AI tool users are likely to be comfortable on macOS;
- current development machine is macOS;
- first packaging scope stays small;
- signing/notarization can be solved once before expanding platform support.

### 3.2 Platform Expansion Order

Recommended order:

```text
1. macOS Apple Silicon
2. macOS Universal / Intel support
3. Windows
4. Linux AppImage / tarball
```

Do not attempt multi-platform packaging in v0.

---

## 4. Packaging Architecture

### 4.1 Runtime Shape

```text
Plato.app
  -> Electron main process
  -> bundled React/TypeScript/Vite frontend
  -> Python backend sidecar
  -> local data/config/log directories
```

The user sees one desktop application.

Internally, the app may have two processes:

```text
Electron desktop shell
Python backend sidecar
```

This split is acceptable only if it is invisible to the user.

### 4.2 Startup Flow

```text
User double-clicks Plato.app
  -> Electron main process starts
  -> Electron starts Python sidecar
  -> sidecar listens on 127.0.0.1 random available port
  -> startup creates local auth token
  -> Electron waits for /health
  -> renderer loads UI
  -> UI talks to backend with local token
```

On app quit:

```text
Electron quits
  -> sidecar receives shutdown signal
  -> sidecar flushes logs/state
  -> sidecar exits
  -> Electron force-kills stale sidecar if graceful shutdown fails
```

### 4.3 Communication

v0 recommendation:

```text
HTTP/WebSocket over 127.0.0.1
random port
per-launch local auth token
```

Reasons:

- easy to debug;
- works well with frontend dev tooling;
- does not force early IPC abstraction;
- can later move to IPC if needed.

Security rules:

- bind only to `127.0.0.1`;
- never bind to `0.0.0.0`;
- require local auth token for renderer/backend calls;
- do not print token into ordinary logs;
- backend should reject requests without token.

---

## 5. Technology Decisions

| Layer | Decision | Reason |
|---|---|---|
| Desktop shell | Electron | Mature packaging/signing ecosystem, lower engineering risk. |
| Frontend | React + TypeScript + Vite | Strong ecosystem for complex Task-first UI. |
| Backend | Python sidecar | Reuses current server-core implementation. |
| Backend packaging | PyInstaller | Mature, fast, enough for v0. |
| Communication | Local HTTP/WebSocket | Simple, debuggable, compatible with web frontend. |
| Distribution | DMG | Familiar macOS install flow. |
| Updates | Manual in v0 | Avoid early auto-update complexity. |
| Secrets | macOS Keychain preferred | Trust point for API keys. |

v0 optimizes for reliability and iteration speed, not minimal package size.

Electron's resource cost is acceptable for early users. If Plato gains traction, Tauri or a lighter shell can be reconsidered later.

---

## 6. App Bundle Shape

Expected app bundle:

```text
Plato.app/
  Contents/
    Info.plist
    MacOS/
      Plato                 # Electron entry binary
      plato-backend          # PyInstaller-built Python sidecar
    Resources/
      app.asar or frontend/
      app-icon.icns
      default-config/
```

All nested executables and native libraries must be signed during release packaging.

---

## 7. User-Facing Deliverables

### 7.1 Trusted Alpha

For self-testing or 1-3 highly trusted users only:

```text
Plato-mac-arm64-v0.1.0.zip
or
Plato-mac-arm64-v0.1.0-unsigned.dmg
```

Unsigned/ad-hoc builds are acceptable only for highly trusted users who understand macOS security warnings.

### 7.2 Closed Beta

For any non-familiar early user:

```text
Plato-mac-arm64-v0.1.0.dmg
SHA256SUMS.txt
RELEASE_NOTES.md
PRIVACY_BETA.md
README_FIRST_RUN.md
```

The DMG should be:

```text
Developer ID signed
notarized by Apple
stapled
```

### 7.3 Public Beta

Same as closed beta, but with stronger polish:

- signed and notarized DMG;
- first-run onboarding;
- provider connection test;
- diagnostic bundle export;
- release notes;
- basic FAQ;
- uninstall instructions;
- stable data directory;
- clear manual update process.

`.pkg` installer is not planned for v0.

---

## 8. Signing And Notarization

### 8.1 Policy

Unsigned packages are only for extremely small, high-trust testing.

```text
Internal Dev    -> unsigned app bundle
Trusted Alpha   -> unsigned/ad-hoc zip or dmg for 1-3 trusted testers
Closed Beta     -> signed + notarized dmg
Public Beta     -> signed + notarized dmg
```

Signing is not polish. For Plato, it is a trust requirement.

Plato may read a workspace, modify files, store provider credentials, and produce local logs. A macOS security warning would damage user trust before the product experience begins.

### 8.2 Direct Cost

Apple Developer Program membership is required for Developer ID distribution.

Current official pricing:

```text
99 USD per membership year
```

Apple says prices may vary by region and local currency. Apple China help pages also describe the annual fee as 99 USD or local currency where applicable.

Notarization itself is not normally a separate per-app fee. The main direct cost is Apple Developer Program membership.

Official references:

- Apple Developer Program enrollment: https://developer.apple.com/programs/enroll/
- Apple Developer Program membership details: https://developer.apple.com/programs/whats-included/
- China membership overview: https://developer.apple.com/cn/programs/whats-included/
- Developer ID: https://developer.apple.com/developer-id/
- Apple Platform Security, app code signing: https://support.apple.com/guide/security/app-code-signing-process-sec3ad8e6e53/web

### 8.3 Signing Inputs

Release packaging needs:

- Apple Developer Program membership;
- Developer ID Application certificate;
- Xcode Command Line Tools;
- `codesign`;
- `xcrun notarytool`;
- hardened runtime;
- notarization credentials;
- CI/local release key management.

### 8.4 Signing Flow

Typical release flow:

```text
build frontend
build python backend arm64 executable
assemble Plato.app
codesign nested binaries
codesign Plato.app
create dmg
codesign dmg
xcrun notarytool submit Plato.dmg --wait
xcrun stapler staple Plato.dmg
verify dmg on a clean machine
```

Validation commands may include:

```text
codesign --verify --deep --strict --verbose=2 Plato.app
spctl --assess --type execute --verbose Plato.app
spctl --assess --type open --context context:primary-signature --verbose Plato.dmg
```

Exact command scripts should be written in the implementation packaging session.

---

## 9. Local Data And Secrets

### 9.1 App Data

Use:

```text
~/Library/Application Support/Plato/
```

Suggested layout:

```text
~/Library/Application Support/Plato/
  config.json
  logs/
  sessions/
  cache/
  diagnostics/
```

### 9.2 Workspaces

Default workspace root:

```text
~/Documents/PlatoWorkspaces/
```

Users should be able to choose another workspace.

Important rule:

```text
Plato should only operate inside user-selected workspace roots.
```

### 9.3 API Keys

Preferred:

```text
macOS Keychain
```

If Keychain support is delayed, closed alpha may temporarily store provider config locally with a clear beta warning. Public beta should not rely on plaintext local key storage.

First-run setup should include:

- provider selection;
- API key entry;
- connection test;
- local storage explanation;
- option to remove key.

---

## 10. First-Run Experience

Recommended first-run flow:

```text
Welcome to Plato
  -> choose workspace
  -> configure LLM provider / API key
  -> test provider connection
  -> show privacy and beta limitations
  -> start sample task or blank session
```

The user should not see implementation details such as TaskWeavn, backend sidecar, port numbers, Python, Electron, or internal architecture terms.

---

## 11. Diagnostics

v0 should include a basic diagnostic export.

User action:

```text
Export Diagnostic Bundle
```

Output:

```text
plato-diagnostics-YYYY-MM-DD-HHMM.zip
```

Include:

- app version;
- OS version;
- architecture;
- config summary;
- recent app logs;
- recent backend logs;
- failed task/session id if available;
- sanitized error reports.

Exclude by default:

- API keys;
- full user file contents;
- full chat/task content unless user explicitly includes it;
- provider secrets;
- local auth token.

This is important for closed beta support.

---

## 12. Manual Update Strategy

v0 does not include auto-update.

Update flow:

```text
User downloads new DMG
User replaces old Plato.app
Plato starts
Plato checks local data schema version
Plato migrates or warns if incompatible
```

Need:

- app version;
- data schema version;
- migration record;
- release notes;
- clear rollback warning if needed.

Auto-update should be deferred until public beta is stable.

---

## 13. Packaging Pipeline

### 13.1 Internal Build

```text
1. clean build artifacts
2. install frontend dependencies
3. install backend dependencies
4. run frontend lint/typecheck/tests
5. run backend lint/typecheck/tests
6. build frontend
7. build Python sidecar with PyInstaller
8. assemble Plato.app
9. run local smoke test
```

### 13.2 Release Build

```text
1. run full tests
2. build frontend
3. build Python sidecar arm64
4. assemble Plato.app
5. sign nested binaries
6. sign Plato.app
7. create DMG
8. sign DMG
9. notarize DMG
10. staple notarization ticket
11. verify Gatekeeper assessment
12. generate SHA256SUMS.txt
13. write RELEASE_NOTES.md
14. smoke test on a clean macOS user account or clean machine
```

---

## 14. Acceptance Criteria

### Trusted Alpha Build

- User can double-click `Plato.app`.
- UI starts without terminal.
- Python backend starts automatically.
- User can choose workspace.
- User can configure provider key.
- User can run one demo flow.
- Logs are written to Application Support.
- App quit cleans up backend sidecar.

### Closed Beta Build

- DMG is signed and notarized.
- Gatekeeper does not show scary malware warning.
- First-run onboarding works.
- API key storage is trustworthy or clearly explained.
- Diagnostic export exists.
- Privacy beta note exists.
- Manual update path is documented.

### Public Beta Build

- Signed/notarized DMG is reproducible.
- Clean-machine smoke test passes.
- Data directory and schema version are stable.
- User can uninstall or reset local data.
- Release notes and FAQ are available.
- Non-technical users do not need command-line instructions.

---

## 15. Implementation Slices

### Slice 1 — Electron Shell Prototype

Deliver:

- Electron app launches;
- React/Vite frontend loads;
- app name and icon use Plato;
- no Python sidecar yet.

### Slice 2 — Python Sidecar Packaging

Deliver:

- PyInstaller builds `plato-backend` arm64 executable;
- backend exposes `/health`;
- backend writes logs under Application Support.

### Slice 3 — Sidecar Lifecycle

Deliver:

- Electron starts sidecar;
- random localhost port;
- per-launch local token;
- renderer connects to backend;
- app quit shuts down sidecar;
- UI displays clear backend startup errors.

### Slice 4 — Local Data And Secrets

Deliver:

- Application Support directory;
- workspace selection;
- provider settings;
- macOS Keychain integration or temporary beta storage with warning;
- provider connection test.

### Slice 5 — DMG Build

Deliver:

- `Plato.app`;
- DMG generation;
- README / privacy beta note;
- release artifact directory.

### Slice 6 — Signing And Notarization

Deliver:

- Developer ID signing;
- notarization;
- stapling;
- verification scripts;
- signed/notarized closed beta DMG.

### Slice 7 — Diagnostic Bundle

Deliver:

- export diagnostics action;
- sanitized zip bundle;
- support instructions.

### Slice 8 — Release Checklist

Deliver:

- clean-machine smoke checklist;
- release notes template;
- manual update instructions;
- uninstall/reset instructions.

---

## 16. Deferred

- Auto-update;
- Windows packaging;
- Linux packaging;
- `.pkg` installer;
- Mac App Store distribution;
- Tauri rewrite;
- remote backend;
- multi-user deployment;
- organization deployment.

---

## 17. Summary

The v0 packaging goal:

```text
Plato feels like one local desktop app.
The user double-clicks once.
Frontend and backend are invisible implementation details.
Non-familiar users receive a signed and notarized DMG.
```

This packaging plan favors trust, stability, and iteration speed over minimal package size.
