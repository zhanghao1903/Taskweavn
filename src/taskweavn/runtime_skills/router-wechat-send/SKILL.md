---
skill_id: internal:router-wechat-send
name: router-wechat-send
description: Use when free-form user input asks Plato to create a task that sends one WeChat message to one contact.
context_requirements:
  - runtime_input_router
  - wechat_send
risk_tags:
  - external_message
  - computer_use
  - high_risk
output_contract: Propose a confirmation-gated communication.wechat.send_message task request draft with contactDisplayName and messageText.
---

# Router WeChat Send

Use this skill to recognize a request to send one WeChat message.

Examples:

- "给微信的文件传输助手发送“你好”"
- "用微信给文件传输助手发消息：你好"
- "在微信给张三发送：明天十点开会"

Required slots:

- `contactDisplayName`: the WeChat contact display name.
- `messageText`: the exact message to draft and send after confirmation.

Task draft:

```json
{
  "taskType": "communication.wechat.send_message",
  "instructions": "Send one confirmation-gated WeChat message.",
  "input": {
    "contactDisplayName": "文件传输助手",
    "messageText": "你好"
  },
  "policy": {
    "requiredCapability": "communication.wechat_desktop_send",
    "requiresHumanConfirmation": true,
    "riskLevel": "high"
  }
}
```

Rules:

1. This is an execution request, not a direct answer.
2. Never propose a send without `requiresHumanConfirmation=true`.
3. Never propose bulk messaging or multiple contacts in the first slice.
4. If contact or message is missing, return clarification.
5. If the user asks to send to a group, broadcast, or unknown contact set,
   return unsupported or clarification.
6. Do not include "发送前让我确认" style safety phrases in `messageText`.
