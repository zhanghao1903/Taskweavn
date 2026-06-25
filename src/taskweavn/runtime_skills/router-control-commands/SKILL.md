---
skill_id: internal:router-control-commands
name: router-control-commands
description: Use when free-form user input may be a product control command such as stop, retry, resume, cancel, pause, or continue.
context_requirements:
  - runtime_input_router
  - router_control_commands
risk_tags:
  - product_state
output_contract: Propose existing_command only when the requested control action is supported by current selected scope and backend state.
---

# Router Control Commands

Use this skill to interpret natural-language product control input.

Control examples:

- "stop", "停止", "停止当前任务", "不要继续执行" -> stop selected running task if one is selected or active.
- "retry", "重试", "再试一次", "重新执行这个任务" -> retry selected failed or retryable task.
- "resume", "继续", "继续执行" -> resume only when a resumable paused/waiting state exists.
- "cancel", "取消", "放弃这个操作" -> cancel pending operation only when backend exposes a cancelable target.

Rules:

1. Do not create a new task for a control command.
2. Do not guess the target if the session has no selected or active task.
3. If the target is ambiguous, return clarification.
4. If the command is unsupported in the current state, return unsupported.
5. The backend validator owns final permission and state checks.
