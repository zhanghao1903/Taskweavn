# Plato Product 1.1 Beta External Release Notes

> Status: public-facing source notes ready
>
> Last Updated: 2026-06-24
>
> Audience: external users, reviewers, and release readers
>
> Internal evidence:
> [Product 1.1 Runtime Input Router Release Evidence](product-1-1-runtime-input-router-release-evidence.md)

## Summary

Plato Product 1.1 beta is a local-first, task-centered workbench for turning
user intent into visible, inspectable work.

This beta closes the Product 1.1 collaboration loop:

```text
user input
  -> Router interpretation
  -> read-only answer, guidance, ASK / confirmation answer, or execution handoff
  -> durable Conversation / Activity
  -> Audit, diagnostics, workspace evidence, and restart-safe replay
```

The release remains a beta. It is intended for local evaluation and technical
review, not broad consumer distribution.

## What Is New In Product 1.1 Beta

### One Input Surface

The Main Page input now routes through the Runtime Input Router. The user can
ask a question, add guidance, answer an ASK / confirmation prompt, request a
Plan or Task change, or ask Plato to create executable work from the same
surface.

### Durable Conversation And Activity

User-visible work is recorded as Session conversation and Activity, not only as
background state changes. Router interpretation, user input, read-only answers,
question cards, command outcomes, task updates, and Plan archive events can be
reloaded and inspected later.

### Read-Only Inquiry

Plato can answer questions about the current Session or workspace without
changing files or product state. Read-only answers include evidence references
where available and are marked as no-effect work.

### Contract Revision Commands

Guidance, ASK answers, confirmation answers, Plan / TaskNode edits, and
execution handoff use command-backed product behavior. The Router decides what
kind of input it received; mutation still goes through accepted domain
commands.

### Workspace Evidence

Product 1.1 includes the workspace inspection foundation: changed-file
projection, file viewer / diff entry points, precision file tools, evidence
links, Audit references, and diagnostic descriptors.

### Runtime And Release Confidence

The beta has passed configured Electron, packaged app, mounted installer,
repo-mode sidecar restart replay, and launcher-packaged sidecar restart replay
smoke checks.

## Verified Release Scope

The internal Product 1.1 beta evidence covers:

- Runtime Input Router route matrix;
- ASK and confirmation routed input;
- read-only inquiry with no workspace mutation;
- command-backed guidance;
- execution handoff instead of direct Router workspace writes;
- durable Conversation / Activity replay after renderer reload;
- Audit navigation and diagnostic bundle export;
- packaged Electron app with bundled Python;
- unsigned `1.1-beta` macOS DMG smoke;
- sidecar restart replay in repo mode and launcher-packaged mode.

## Release Artifact

Current internal beta artifact:

```text
frontend/dist-electron-installer/Plato-1.1-beta-macos-arm64.dmg
```

| Field | Value |
|---|---|
| Version | `1.1-beta` |
| Runtime | Bundled Python sidecar |
| SHA256 | `fa67d9441d45537e6f59d674f03811fe10fcbf936da5986e12e6aef846e9406e` |
| Signed | No |
| Notarized | No |

External publishing should attach the DMG as a release asset instead of
committing it to Git.

## Known Limitations

- The macOS beta DMG is unsigned and not notarized.
- The app is local-first and early-user focused; it is not a hosted SaaS.
- Sidecar restart replay is covered in repo-mode and launcher-packaged smoke,
  but has not yet been folded into mounted-installer smoke.
- Optional LLM-rendered read-only inquiry smoke remains beta-depth evidence.
- Web retrieval exists as a backend capability, but public-facing citation UX
  and broader real-provider release evidence still need hardening.
- Stop / cancel UX still needs product polish so intentional user stops do not
  feel like generic failures.
- Some UI copy remains mixed between English and Chinese.
- Public skill marketplace, custom Agent protocol, broad MCP integration,
  multimodal input, signed distribution, and remote execution are not part of
  this beta release.

## Safe Public Claims

Use these claims when writing public release material:

- Plato is a local-first, task-centered workbench.
- Product 1.1 beta adds a Router-first input loop and durable Session
  conversation / Activity.
- Plato can distinguish questions, guidance, ASK / confirmation answers, and
  execution requests through one input surface.
- Workspace-changing requests are routed into executable work instead of direct
  Router writes.
- Audit and diagnostics are first-class trust surfaces.
- The current beta is unsigned, not notarized, and intended for technical
  evaluation.

Avoid these claims:

- "Production ready."
- "Fully autonomous."
- "Secure" without explaining local-first storage, confirmation, audit, and
  current limits.
- "Multi-agent marketplace ready."
- "MCP / multimodal support shipped."
- "Signed macOS release."

## Suggested External Release Checklist

Before publishing this beta externally:

1. Attach the DMG as a release asset.
2. Publish the SHA256 checksum next to the asset.
3. Link these release notes from the public README.
4. Make the unsigned / not-notarized caveat visible before download.
5. Include a short feedback path for beta testers.
6. Keep screenshots public-safe and aligned with the Product 1.1 UI.

## Evidence Links

- [Product 1.1 Runtime Input Router Release Evidence](product-1-1-runtime-input-router-release-evidence.md)
- [Product 1.1 P0 Release Evidence](../product/plato-1-1-p0-release-evidence-2026-06-20.md)
- [Product 1.1 Open Work](../product/plato-1-1-open-work.md)
- [Plato Public Exposure Planning](../product/public-exposure/README.md)
