---
skill_id: internal:router-task-authoring
name: router-task-authoring
description: Use when free-form user input should create, revise, or clarify a task or plan instead of being answered directly.
context_requirements:
  - runtime_input_router
  - task_authoring
risk_tags:
  - product_state
output_contract: Propose task or plan changes only through command-backed or execution-handoff drafts.
---

# Router Task Authoring

Use this skill when the user asks Plato to do work.

Task-authoring examples:

- "帮我实现 ASK Dock 前端" -> create or update a task/plan.
- "把这个任务改成先写测试" -> propose a task or plan patch if a command-backed path exists.
- "打开微信给文件传输助手发消息" -> create an execution task, not a read-only answer.

Rules:

1. Do not mutate plans directly.
2. Use command-backed drafts for product-state changes.
3. Use execution handoff for workspace-changing or external-system work.
4. Ask clarification when the goal, target, or required inputs are missing.
5. A single user input should produce one primary task/plan side effect.
