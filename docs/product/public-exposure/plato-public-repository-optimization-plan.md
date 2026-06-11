# Plato Public Repository Optimization Plan

> Status: implementation-ready plan
> Last Updated: 2026-06-11
> Target Repository: `zhanghao1903/plato-public`
> Related Exposure Plan: [Plato Public Exposure Plan](plato-public-exposure-plan.md)
> Visual Gap Tracker: [Public Visual Asset Gaps](public-visual-asset-gaps.md)

---

## 1. Purpose

This plan turns the public repository review into an implementation guide.

The public repository is no longer just a release shell. It now contains a
README, product docs, architecture docs, usage docs, release metadata, and
visual assets. The next optimization pass should make it feel like a friendly
public product surface for two audiences:

| Audience | What they need first | What should be easy to find |
|---|---|---|
| Ordinary users | What Plato does, whether it is safe to try, how to start, what is currently limited. | Download, quickstart, examples, FAQ, privacy/safety, screenshots. |
| Recruiters / reviewers | Why the product is interesting, what has been built, what engineering quality it demonstrates. | Product thesis, architecture overview, trust model, technical highlights, release status, evidence of working app. |

The core optimization goal:

```text
Make the public repository understandable in 60 seconds,
tryable in 5 minutes,
and credible in 15 minutes.
```

## 2. Current State Summary

Current public repo strengths:

- It already has a downloadable `0.1.0` macOS Apple Silicon release.
- It separates product docs, architecture docs, usage docs, release metadata,
  screenshots, and explanatory images.
- It has a strong product thesis around task-first work, the Control Plane,
  and the Trust Plane.
- It has useful screenshots and diagrams for Main Page, Audit Page, ASK, and
  workspace inspection.

Current weaknesses:

- The first screen still reads closer to "product philosophy plus release
  repository" than a user-facing product landing page.
- The value proposition needs to be more direct before introducing the
  Inspiration / Control / Trust plane language.
- Ordinary users need a clearer "what can I do with this?" path.
- Recruiters need a clearer "what does this demonstrate technically?" path.
- The release caveats are important, but they should not dominate before the
  product is understood.
- Quickstart, FAQ, engineering highlights, and privacy/safety docs should be
  first-class public surfaces.

## 3. Public Positioning

Use this as the leading public message:

```text
Plato turns vague goals into visible task plans,
runs work locally,
and keeps an audit trail so users stay in control.
```

Secondary message:

```text
Chat is good for conversation.
Plato is built for work that needs planning, confirmation, and trust.
```

Do not lead with:

- internal runtime names;
- raw architecture object names;
- "multi-agent" claims before the Task-first model is explained;
- broad autonomous-agent promises;
- release checksum details before product explanation.

## 4. README Optimization Direction

The README should behave like a product landing page, not only a repository
index.

Recommended README order:

1. Hero: product name, one-line value proposition, main screenshot.
2. Primary CTAs:
   - download macOS Apple Silicon release;
   - quickstart;
   - user guide;
   - architecture overview.
3. "Why Plato": clear comparison with chat assistants and coding agents.
4. "How it works": goal -> plan -> review -> execute -> audit.
5. "What you can try today": three or four concrete use cases.
6. Product screenshots: Main Page, Audit Page, ASK, workspace inspection.
7. Release status: local RC, unsigned/non-notarized, bundled sidecar.
8. For users: quickstart, FAQ, safety/privacy, troubleshooting.
9. For reviewers: engineering highlights, architecture, trust/audit model.
10. Current limitations and roadmap boundaries.

Recommended README opening:

```md
# Plato

Turn vague goals into visible task plans, run them locally, and inspect what happened.

Plato is a task-first intelligent workbench. Instead of hiding work in a long
chat transcript, it turns a goal into a plan, lets you review and guide each
task, asks for confirmation when needed, and keeps an audit trail afterward.
```

## 5. Information Architecture Changes

### 5.1 Keep And Strengthen Existing Public Files

| Public file | Action | Implementation guidance |
|---|---|---|
| `README.md` | Rewrite as landing page. | Keep release links, screenshots, and docs map, but lead with user value and concrete examples. |
| `docs/product/overview.md` | Keep. | Ensure it links back to the new quickstart and use cases. |
| `docs/product/task-first-workflow.md` | Keep. | Make this the deeper explanation after the README's shorter "How it works" section. |
| `docs/product/release-status.md` | Keep. | Keep the caveats precise; link from README after product explanation. |
| `docs/architecture/overview.md` | Keep. | Make it the recruiter/reviewer architecture entry. |
| `docs/architecture/trust-and-audit.md` | Keep. | Link from README's Trust section and safety/privacy doc. |
| `docs/usage/user-guide.md` | Keep. | Treat as complete guide, not quickstart. |
| `docs/usage/macos-local-release.md` | Keep. | Link from quickstart and release status. |

### 5.2 Add Public User Documents

| New file | Audience | Purpose |
|---|---|---|
| `docs/usage/quickstart.md` | Ordinary users and reviewers | A short path from download to first successful run. Should be readable before the full user guide. |
| `docs/usage/faq.md` | Ordinary users | Answers predictable questions: Is it safe? Does it edit files? Why unsigned? Where is data stored? What works today? |
| `docs/product/use-cases.md` | Ordinary users and reviewers | Shows concrete tasks Plato can help with, without implying unsupported automation. |
| `docs/security/privacy-and-safety.md` | Ordinary users and reviewers | Explains local-first behavior, confirmation, audit, logs, and current limits. |

### 5.3 Add Public Reviewer / Recruiter Documents

| New file | Audience | Purpose |
|---|---|---|
| `docs/engineering/highlights.md` | Recruiters / technical reviewers | Summarizes architecture and engineering decisions in a way that is impressive but not private. |
| `docs/releases/0.1.0.md` or `CHANGELOG.md` | Users and reviewers | Human-readable release notes separate from machine-readable manifest/checksum files. |

### 5.4 Add Repository Operations Files

| New file | Priority | Notes |
|---|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | P2 | Helps external testers report reproducible issues. |
| `.github/ISSUE_TEMPLATE/feedback.yml` | P2 | Captures product feedback from ordinary users. |
| `.github/ISSUE_TEMPLATE/question.yml` | P2 | Reduces vague issues. |
| `LICENSE` | P2 / blocked | Do not add until the license decision is explicit. |
| `SECURITY.md` | P2 | Optional; useful if public testers are invited. |

## 6. Content Requirements By Audience

### 6.1 Ordinary User Path

The public repo should answer these questions quickly:

1. What is Plato?
2. Can I try it without being a developer?
3. What does it do differently from ChatGPT or Claude?
4. Will it modify my files?
5. When does it ask me before acting?
6. How do I inspect what happened?
7. What does the current release not do yet?

Recommended user-facing path:

```text
README
  -> Quickstart
  -> User Guide
  -> FAQ
  -> Privacy and Safety
  -> Release Status
```

### 6.2 Recruiter / Reviewer Path

The public repo should answer these questions quickly:

1. What product problem is this solving?
2. What is technically interesting?
3. What architecture decisions are visible?
4. What has actually shipped?
5. How does the system handle trust, audit, and local execution?
6. What is next?

Recommended reviewer-facing path:

```text
README
  -> Engineering Highlights
  -> Architecture Overview
  -> Trust And Audit
  -> Release Status
  -> Public assets / screenshots
```

## 7. Claim And Status Rules

Every public statement should fit one of these status labels:

| Label | Meaning | Example wording |
|---|---|---|
| Available in `0.1.0` | A user can verify it in the current public release. | "The Main Page shows task plans and task status." |
| Current development preview | Implemented or visible in development, but not guaranteed in the public release. | "Workspace inspection is being developed as the next trust surface." |
| Roadmap | Product direction only. | "Future releases should expand the Inspiration Plane." |
| Concept | Product philosophy or positioning. | "Plato is task-first rather than chat-first." |

Avoid ambiguous public claims such as:

- "Plato automatically solves any task."
- "Multi-agent orchestration is ready."
- "Workspace inspection is fully shipped" unless the public release artifact
  actually includes the verified feature.
- "Secure" without explaining concrete controls.

## 8. Implementation Slices

### PUB-OPT-001: README Landing Rewrite

Goal: make the repository understandable in the first screen.

Changes:

- Rewrite README hero and opening.
- Add direct CTAs.
- Add "Why Plato" comparison.
- Add a short "How it works" flow.
- Move release caveats below product understanding.
- Add separate paths for users and reviewers.

Acceptance:

- A new visitor can explain Plato in one sentence after reading the top third.
- Download, quickstart, user guide, and architecture links are visible.
- No unsupported feature is presented as generally available.
- Existing release link and checksum references remain correct.

### PUB-OPT-002: Quickstart And FAQ

Goal: make the product tryable and approachable.

Changes:

- Add `docs/usage/quickstart.md`.
- Add `docs/usage/faq.md`.
- Link both from README and `docs/usage/user-guide.md`.

Acceptance:

- Quickstart covers download, unsigned macOS open flow, first session, first
  plan, confirmation, and audit.
- FAQ covers unsigned app warning, local execution, file modification,
  confirmation, logs, data storage, current limitations, and issue reporting.
- User guide remains the longer reference.

### PUB-OPT-003: Use Cases

Goal: show why ordinary users should care.

Changes:

- Add `docs/product/use-cases.md`.
- Include 5-7 concrete use cases with:
  - user goal;
  - what Plato turns it into;
  - what the user reviews;
  - what evidence or result to inspect;
  - release availability note.

Suggested use cases:

- personal website planning;
- content page creation;
- local project cleanup;
- research-to-task breakdown;
- bug-fix planning;
- learning material / courseware drafting;
- result inspection and acceptance.

Acceptance:

- Examples are concrete enough for non-technical users.
- Technical examples do not dominate the page.
- Each use case makes the Task-first loop visible.

### PUB-OPT-004: Engineering Highlights

Goal: make the project credible to recruiters and technical reviewers.

Changes:

- Add `docs/engineering/highlights.md`.
- Link it from README's reviewer path.

Recommended sections:

- Task-first product model;
- local sidecar architecture;
- Main Page projection model;
- Audit Page / trust plane;
- confirmation and ASK flow;
- context governance;
- packaged Electron app with bundled Python sidecar;
- release QA and checksum discipline.

Acceptance:

- Reads like engineering judgment, not a raw code inventory.
- Does not copy private implementation details that should stay internal.
- Explains why choices were made, not only what exists.

### PUB-OPT-005: Privacy And Safety

Goal: reduce user fear and avoid overclaiming.

Changes:

- Add `docs/security/privacy-and-safety.md`.
- Link from README, FAQ, and release status.

Recommended sections:

- local-first release model;
- what data may be stored locally;
- logs and audit;
- confirmation before risky actions;
- what the app does not promise yet;
- how to report concerns.

Acceptance:

- Uses plain language.
- Makes the unsigned/local RC caveat clear.
- Does not claim formal security guarantees.

### PUB-OPT-006: Release Notes

Goal: separate human release notes from machine metadata.

Changes:

- Add `docs/releases/0.1.0.md` or `CHANGELOG.md`.
- Link manifest and checksum files.
- Link GitHub Release `v0.1.0`.

Acceptance:

- Users can see what the release includes and does not include.
- Release caveats are not buried.
- The large DMG remains a GitHub Release asset, not a Git-tracked file.

### PUB-OPT-007: Feedback Intake

Goal: make external feedback useful.

Changes:

- Add issue templates for bug reports, product feedback, and questions.
- Optional: add a short "How to give feedback" README section.

Acceptance:

- Bug reports ask for OS, version, reproduction steps, expected behavior,
  actual behavior, screenshots/log excerpts if safe, and release version.
- Feedback asks for user goal, confusing step, expected product behavior, and
  whether the user is technical/non-technical.

## 9. Public README Content Skeleton

```md
# Plato

Turn vague goals into visible task plans, run them locally, and inspect what happened.

![Plato Main Page](assets/screenshots/plato-main-page.png)

[Download for macOS Apple Silicon](...) [Quickstart](docs/usage/quickstart.md)
[User Guide](docs/usage/user-guide.md) [Architecture](docs/architecture/overview.md)

## Why Plato

Chat is good for conversation. Plato is built for work.

- Plan before action.
- Review tasks before they run.
- Confirm risky steps.
- Inspect results and audit evidence.

## How It Works

1. Describe a goal.
2. Plato drafts a plan.
3. You review or refine tasks.
4. Plato runs the approved work locally.
5. You inspect results, file changes, and audit evidence.

## What You Can Try Today

...

## Current Release

...

## For Users

...

## For Reviewers

...
```

## 10. Public Copy Guidelines

Use:

- short paragraphs;
- concrete examples;
- screenshots before deep architecture;
- "local release candidate" when discussing `0.1.0`;
- "audit trail" and "evidence" only with examples;
- "task plan" before "TaskTree" for ordinary users.

Avoid:

- "autonomous employee";
- "one-click do everything";
- "agent swarm";
- unexplained "TaskBus", "EventStream", "Context Manager" in README top
  sections;
- private branch names and internal PR history;
- screenshots with real user data, private paths, or local usernames.

## 11. Visual Requirements

The current visual set is good enough for a first public pass, but the README
should use visuals in this order:

1. Main Page screenshot.
2. Product flow diagram.
3. Audit Page screenshot.
4. Architecture overview for reviewers.

Every image reference should include:

- useful alt text;
- short caption if the surrounding section needs it;
- status note if the image shows a preview feature not in `0.1.0`.

## 12. QA Checklist For Public Repo Changes

Before opening the public repo optimization PR:

- README links resolve.
- Download link points to the GitHub Release asset, not a Git-tracked DMG.
- `releases/0.1.0/manifest.json` and `SHA256SUMS` are unchanged unless a
  release update is intentional.
- No large binary DMG is staged.
- No private path, username, API key, branch-only claim, or internal screenshot
  leaks into public docs.
- Public docs distinguish:
  - available in `0.1.0`;
  - current development preview;
  - roadmap;
  - concept.
- Screenshots have public-safe sample data.
- Markdown renders cleanly on GitHub.
- Issue templates, if added, are valid YAML.

## 13. Open Decisions

| Decision | Why it matters | Recommendation |
|---|---|---|
| License | Public users need to know usage rights. | Do not add a license until the owner chooses one explicitly. |
| Source code exposure | The public repo currently distributes product docs and releases, not source. | Keep public repo product/release-focused for now. |
| Public feedback policy | External users may open vague issues. | Add issue templates before broader sharing. |
| Public demo video | A short video would improve ordinary user understanding. | Defer until the Main Page and Audit Page visuals stabilize. |
| Website / GitHub Pages | A public site may be better than README-only for non-technical users. | Consider after README and docs are coherent. |

## 14. Recommended Execution Order

P0:

1. `PUB-OPT-001` README landing rewrite.
2. `PUB-OPT-002` quickstart and FAQ.
3. `PUB-OPT-006` release notes.

P1:

4. `PUB-OPT-003` use cases.
5. `PUB-OPT-004` engineering highlights.
6. `PUB-OPT-005` privacy and safety.

P2:

7. `PUB-OPT-007` feedback intake.
8. License decision.
9. Demo video or animated walkthrough.

This order prioritizes user friendliness first, credibility second, and
repository operations third.
