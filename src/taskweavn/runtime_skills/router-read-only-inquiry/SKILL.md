---
skill_id: internal:router-read-only-inquiry
name: router-read-only-inquiry
description: Use when free-form user input asks a question that should be answered without mutating product state or workspace files.
context_requirements:
  - runtime_input_router
  - read_only_inquiry
risk_tags:
  - no_mutation
output_contract: Use read_only_inquiry with safe refs or context requests. Never propose workspace mutation for answer-only questions.
---

# Router Read-Only Inquiry

Use this skill when the user asks a question or asks Plato to inspect current
state without changing anything.

Examples:

- "现在任务进展怎么样？" -> read-only inquiry over session/task facts.
- "为什么没有 LLM 日志？" -> read-only inquiry over diagnostics/config facts if available.
- "README 里怎么启动项目？" -> request safe file context, then read-only inquiry.
- "当前 diff 改了什么？" -> request safe diff context, then read-only inquiry.

Rules:

1. Use `sideEffect=no_effect`.
2. Do not write files, create tasks, or run shell commands.
3. If file/diff/search context is needed, request validated read-only refs.
4. If the user asks to implement, edit, run, send, or publish, this is not a
   read-only inquiry.
5. If evidence is unavailable, explain the limitation instead of inventing facts.
