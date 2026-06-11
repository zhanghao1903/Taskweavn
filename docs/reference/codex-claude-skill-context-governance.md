# Codex / Claude Skills And Context Governance Research

> Status: reference research
> Last Updated: 2026-06-11
> Scope: Product 1.1 skill/context design input, not an implementation plan

## 1. Research Question

Taskweavn Product 1.1 is considering skill support. The core question is not
only how to store a skill file, but how skill content should enter the Agent
context without turning every skill into always-on prompt baggage.

This document compares Codex and Claude Skills with a focus on:

- how skills are discovered;
- what part of a skill enters context before activation;
- what part enters context after activation;
- how supporting files and scripts affect context;
- where context governance, permissions, and traceability should connect in
  Taskweavn.

Related local documents:

- [Agent Skills reference](agent-skills.md)
- [Codex context governance engineering](codex-context-governance-engineering.md)
- [Context Manager Architecture](../architecture/context-manager.md)
- [Architecture Overview](../architecture/overview.md)

## 2. Executive Summary

Skills are best understood as context and workflow packages, not as model
weights, durable memory, or raw tools.

Codex and Claude both use progressive disclosure:

1. keep a lightweight skill index in context;
2. load the full skill instructions only when the skill is selected;
3. read supporting references only when needed;
4. run bundled scripts as tools or preprocessing where supported, rather than
   blindly loading script source into the model context.

For Taskweavn, this implies:

- skills should become an explicit Context Manager source;
- skill activation should be traceable and versioned;
- only skill metadata should be broadly available by default;
- active skill instructions should have their own budget and priority;
- skill-provided tool permissions must merge with, not override, runtime
  permission policy;
- skills should not become the place where hidden product state lives.

The current Taskweavn `ExecutionGuidance.active_skills` model is a useful
starting point, but it only carries skill summaries. Product 1.1 still needs a
registry, activation policy, version/hash trace, budget policy, and UI/audit
visibility rules.

## 3. Source Findings

### 3.1 OpenAI Codex Skills

Codex documents skills as reusable workflow packages containing instructions,
resources, and optional scripts. A skill is a directory with a required
`SKILL.md` and optional `scripts/`, `references/`, and `assets/`.

Codex uses progressive disclosure:

- the initial available skill list contains skill name, description, and file
  path;
- Codex reads the full `SKILL.md` only after it decides to use the skill;
- the initial skill list has a context budget, so descriptions may be shortened
  or omitted when too many skills are installed;
- skills can be invoked explicitly by the user or implicitly when the task
  matches the skill description;
- repo, user, admin, and system skill scopes can all contribute skills.

Codex-specific implications:

- `description` is not just documentation; it is part of the activation
  mechanism.
- `SKILL.md` should be compact and procedural. Large references should move to
  separate files.
- Optional Codex metadata can control implicit invocation and declare tool
  dependencies, but tools and permissions are still governed by the runtime.
- Repo-scoped skills such as this repository's `product-workflow-gate` and
  `maintainability-gate` are already examples of skills used as workflow guards.

### 3.2 Claude Skills

Claude Code documents skills as `SKILL.md` files with frontmatter and markdown
instructions. Skills can live at personal, project, plugin, or managed scopes.
Claude can invoke a skill automatically when relevant, or the user can invoke
one directly.

Claude's context behavior is more explicit in public documentation:

- the skill body is not loaded until the skill is used;
- once invoked, rendered skill content enters the conversation context and
  remains there for later turns;
- when the conversation is compacted, recent invoked skills are reattached
  within a bounded token budget;
- supporting files are referenced from `SKILL.md` and loaded only when needed;
- scripts can be executed without loading the script or all input data into the
  model context;
- dynamic context injection can run a command before the model sees the skill
  content, replacing the placeholder with command output;
- a skill can run in a forked subagent context for isolation.

Claude-specific implications:

- skill content has a lifecycle after invocation. It is not simply a one-turn
  prompt.
- skill compaction behavior means old skills may lose influence if many skills
  have been invoked.
- dynamic context injection is powerful but needs policy control because it can
  pull live environment data into the prompt.
- skill-level tool allowances are convenience policy, not a replacement for
  baseline permission rules.

### 3.3 Agent Skills Open Standard

The Agent Skills specification defines the common package shape:

- a skill directory with required `SKILL.md`;
- required `name` and `description` frontmatter;
- optional `scripts/`, `references/`, and `assets/`;
- progressive disclosure from metadata to full instructions to resources.

The standard reinforces the main design point: skills should be structured so
the agent can discover them cheaply and expand only the relevant parts.

## 4. Comparison

| Dimension | Codex | Claude | Taskweavn Implication |
|---|---|---|---|
| Package unit | Directory with `SKILL.md` plus optional resources | Directory with `SKILL.md` plus optional resources | Use filesystem-backed local skills first. |
| Initial context | Name, description, path, bounded list | Skill listing / description metadata | Keep a compact registry index in Session context. |
| Activation | Explicit mention or implicit description match | Direct command or automatic relevance match | Support both explicit user activation and model/router activation. |
| Full instructions | Loaded when selected | Loaded when invoked | Treat active skill body as a separately budgeted context segment. |
| References | Read on demand | Read on demand | Store references as refs first; inline only selected excerpts. |
| Scripts | Optional deterministic helpers | Optional helpers or dynamic context injection | Scripts are tools/preprocessors, not prompt text by default. |
| Permissions | Runtime sandbox/approval still matters | Skill allowed/disallowed tools merge with settings | Runtime permission policy must remain authoritative. |
| Lifecycle | Selected skill instructions affect subsequent work while in context | Invoked skills persist and are reattached through compaction budgets | Taskweavn needs activation trace, expiry, and reactivation rules. |
| Distribution | Local skills and plugins | Personal/project/plugin/managed skills | Product 1.1 can start with local/project skills; marketplace is later. |

## 5. Skill Context Lifecycle Model

Taskweavn should model skills as a staged context source:

```text
Skill registry
  -> skill index metadata
  -> activation decision
  -> active skill context segment
  -> optional reference expansion
  -> optional script/tool result
  -> trace / audit / compaction policy
```

### 5.1 Registry Stage

The registry owns installed skill metadata:

- skill id;
- display name;
- description;
- source path or package id;
- trust level;
- version or content hash;
- supported triggers;
- optional tool requirements;
- optional environment requirements.

Only the compact index should be broadly visible to an Agent.

### 5.2 Activation Stage

A skill can be activated by:

- explicit user request;
- route or task capability match;
- Agent/router selection;
- product policy, such as a required workflow gate;
- file/path context, if later supported.

The activation record should include:

- activated skill id;
- activation reason;
- triggering task/session/user message;
- version/hash at activation time;
- whether activation is user-visible;
- whether it is allowed to affect tool permissions;
- context budget assigned to it.

### 5.3 Active Context Stage

After activation, the Context Manager may include:

- compact skill summary;
- selected `SKILL.md` body or section;
- source references;
- output requirements;
- allowed/denied tool hints;
- caveats such as "reference only" or "do not execute scripts".

This should be represented as a structured context segment rather than merged
into an opaque prompt string.

### 5.4 Resource Expansion Stage

Supporting files should be pulled only when a reason exists:

- the active skill says a reference file is needed;
- the current task type requires that reference;
- the Agent explicitly asks to inspect it through an allowed tool;
- a deterministic preprocessor selected a bounded excerpt.

Large files should not be loaded in full by default.

### 5.5 Tool / Script Stage

Scripts bundled with a skill should be treated as tools or preprocessors:

- script source does not need to enter the model context by default;
- script output can enter context as a summarized tool result;
- side effects must pass the same permission and approval policy as other
  workspace actions;
- all executed script paths and outputs should be traceable.

### 5.6 Compaction / Retention Stage

Taskweavn should not assume that an active skill remains perfectly remembered.
After long execution:

- the active skill summary should remain in `ExecutionGuidance`;
- the full body may be summarized or evicted by policy;
- recent active skills should receive higher retention priority;
- critical workflow gates should be reattached by policy rather than relying on
  model memory.

## 6. Current Taskweavn Gap Analysis

Current code already has partial hooks:

- `SkillSummary` in `src/taskweavn/context/models.py`;
- `ExecutionGuidance.active_skills`;
- `GuidanceContextSource`;
- `ExecutionControls` for allowed/denied tools and approvals;
- `ContextTraceRef` for traceability;
- `FileSnippet.can_act_as_instruction` for instruction trust separation.

Missing or weak pieces:

| Area | Current State | Gap |
|---|---|---|
| Skill registry | Not implemented as a domain source | No canonical installed/available skill index. |
| Skill activation | Manual guidance can include active summaries | No durable activation record or reason. |
| Skill versioning | Not present | No content hash or version trace. |
| Skill body budget | Not modeled | Cannot budget `SKILL.md` separately from events/files. |
| Supporting references | Generic file snippets exist | No skill-specific reference expansion policy. |
| Script execution | Tools exist generally | No skill-script trust, permission, or trace model. |
| Permission merge | Controls exist | No rule for skill-provided allowed/denied tool hints. |
| UI visibility | Not present | User cannot see active skill/capability context. |
| Auditability | Context trace exists | Trace does not explain skill activation and loaded resources. |
| Compaction | Cache-aware context exists | No skill retention/reattachment policy. |

## 7. Recommended Taskweavn Product 1.1 Direction

Product 1.1 should avoid building a full skill marketplace or generic plugin
ecosystem first. The smallest useful slice is local/project skill governance
for execution quality.

Recommended sequence:

1. **Skill Registry v0**
   - Read local/repo skill descriptors.
   - Validate `name`, `description`, path, trust level, and content hash.
   - Expose a compact skill index to Context Manager.

2. **Skill Activation Record**
   - Persist active skill ids per Session or Task run.
   - Record activation reason and source message/task.
   - Include active skill summaries in `ExecutionGuidance`.

3. **Context Manager Integration**
   - Add a `SkillContextSource`.
   - Render skill metadata separately from active skill instructions.
   - Apply a dedicated skill token/character budget.

4. **Permission Policy Merge**
   - Treat skill tool hints as requested permissions.
   - Baseline runtime deny/approval policy remains authoritative.
   - Skill scripts execute only through approved tool pathways.

5. **Trace And Audit**
   - Store active skill id, path, content hash, loaded references, and script
     outputs in context traces.
   - Make active skill context visible in debug/audit surfaces.

6. **UI Exposure**
   - Show active capability/skill as a lightweight task execution fact.
   - Do not require the user to understand skills for ordinary use.

Deferred beyond first slice:

- user-installable skill marketplace;
- cross-session skill learning;
- model-generated skill authoring;
- automatic skill refactoring;
- forked subagent skill execution;
- skill-level prompt cache optimization;
- rich skill ranking/search.

## 8. Design Principles For Taskweavn

### 8.1 Skill Is Context, Tool Is Action

A skill should tell the Agent how to approach a task. A tool changes or reads
the world. Combining them without separation makes permissions and audit harder.

### 8.2 Skill Metadata Is Cheap, Skill Body Is Expensive

Keep the skill index compact and always available. Load full instructions only
when activation is justified.

### 8.3 Skills Must Be Traceable

If a skill influenced an Agent run, Taskweavn should be able to answer:

- which skill was active;
- why it was active;
- which version/hash was used;
- what references were loaded;
- what scripts ran;
- what permission changes were requested or denied.

### 8.4 Skills Must Not Override Product Policy

Skill instructions are advisory workflow context unless the product explicitly
promotes them into policy. Permission, file scope, approval, and user safety
remain runtime-owned.

### 8.5 Skills Should Be User-Invisible By Default But Inspectable

Most users should experience better behavior, not a new configuration burden.
Advanced users and debugging surfaces should expose active skill/capability
facts.

## 9. Open Product Questions

1. Should users be able to explicitly select a skill, or should the first
   product version use only automatic capability routing?
2. Is skill activation Session-scoped, Task-scoped, or Agent-run-scoped by
   default?
3. How should active skills interact with future guidance/command/question
   input classification?
4. Should a skill be allowed to change tool availability, or only request
   permission profile changes?
5. Should skill references be stored as durable context facts for retry and
   audit, or reloaded from disk each run by hash?
6. How much skill information should be visible in Main Page versus Audit Page?
7. How should Taskweavn handle conflicting skills?

## 10. Recommended Next Task

Create a Product 1.1 Skill Governance Plan covering:

- `SkillRegistry` domain boundary;
- `SkillActivation` lifecycle;
- `SkillContextSource` contract;
- context budget policy;
- trust and permission merge rules;
- UI/debug exposure;
- first implementation slice and tests.

The plan should be created before implementing skill loading or letting skills
affect execution context.

## 11. Sources

- OpenAI Codex Manual, Agent Skills section:
  `https://developers.openai.com/codex/codex-manual.md`
- Claude Code Skills documentation:
  `https://docs.claude.com/en/docs/claude-code/skills`
- Anthropic Engineering, Agent Skills context and security discussion:
  `https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills`
- Agent Skills specification:
  `https://agentskills.io/specification`
