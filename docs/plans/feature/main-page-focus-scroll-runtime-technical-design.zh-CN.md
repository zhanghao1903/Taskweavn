# Main Page Focus / Scroll Runtime 技术方案

> Status: implementation slice in progress
>
> Last Updated: 2026-06-26
>
> Owner: Frontend / Interaction Runtime
>
> Branch: `codex/main-page-focus-scroll-runtime`
>
> Related:
> [Main Page Runtime Reducer And Local Pending Submit](main-page-runtime-reducer-local-pending-submit-technical-design.zh-CN.md),
> [Main Page Frontend Runtime Integration](main-page-frontend-runtime-integration.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md),
> [Router-first Main Page Input](router-first-main-input-durable-activity-technical-design.zh-CN.md)

---

## 1. 背景

PR #146 已经把 Main Page 的 local pending submit foundation 合入主线。用户提交
输入后，前端可以在 Conversation 中本地投影 user input 和
`Understanding your request...`，不再完全等待后端 snapshot。

下一步要解决的是交互运行时问题：

- 新消息出现后，Conversation 是否应该滚到底部；
- 用户正在阅读历史内容时，系统是否应该打断滚动位置；
- submit 后 input focus 如何保持或恢复；
- Router/ASK 产生问题卡片时，焦点应该去哪里；
- rejected / failed 路径如何保持用户可继续输入；
- 切换 session/workspace、打开 activity/audit/archived plan 时，focus 和 scroll
  是否应该重置或保留。

当前代码中，`ConversationLayer` 只是渲染一个 `overflow: auto` 的 message list。
`MainPageWorkbench` 负责把 snapshot messages 和 `runtimeActivityItems` 合成
`conversationMessages`，但没有统一的 scroll intent、bottom sentinel、manual scroll
检测或 focus request runtime。因此，交互行为容易散落到组件 effect 中，后续会和
streaming、event patch、ASK card 等能力互相冲突。

---

## 2. 目标

本切片新增一个前端侧 Focus / Scroll Runtime，目标是让 Main Page 的交互变成可预测、
可测试的运行时策略，而不是一次性 DOM effect。

第一版目标：

1. 用户 submit 后，local pending item 出现时自动可见。
2. 如果用户原本位于 Conversation 底部，后续 Router interpretation / answer /
   ASK card / recovery note 追加时继续跟随到底部。
3. 如果用户已经手动向上滚动阅读历史内容，后台追加不强行拉回底部。
4. submit、accepted、rejected、failed、snapshot reconcile 后，input focus 有明确
   恢复规则。
5. Router 发起 ASK 时，问题卡片可被定位和聚焦，但不能形成 focus trap。
6. 该 runtime 与现有 `mainPagePendingRuntime` 集成，不修改后端 API contract。
7. 策略逻辑可通过 reducer/policy 单元测试覆盖，DOM 行为通过 component/Electron
   acceptance 覆盖。

---

## 3. 非目标

- 不实现 token streaming。
- 不修改 backend event payload。
- 不把 Main Page 改成 event patch reducer。
- 不重写 `MainPageWorkbench` 布局。
- 不改变 Activity / Audit / Archived Plan 的信息架构。
- 不修改 ASK 的后端持久化模型。
- 不引入虚拟列表。当前 Conversation 量级先用普通 scroll container。

---

## 4. 当前代码事实

| 区域 | 当前事实 | 对 focus/scroll 的影响 |
|---|---|---|
| Conversation | `ConversationLayer` 接收 `messages` 并渲染 `SessionMessageCard` 列表。 | 没有 list ref、bottom sentinel、message key 变更检测。 |
| CSS | `.conversationMessageList` 是 `overflow: auto`。 | 可以作为 scroll container，但需要 DOM ref 和 scroll policy。 |
| Pending runtime | `useMainPageInputRuntimeState` 通过 `mainPagePendingRuntime` 投影 local items。 | 已有 submit lifecycle，可作为 scroll/focus trigger 来源。 |
| Workbench | `MainPageWorkbench` 合成 `conversationMessages` 和 header actions。 | 适合作为 runtime hook 的组合点，但不应承载复杂策略。 |
| Input | input/button 已有 pending spinner 和 disabled 状态。 | 缺少 input ref、focus request、disabled 后恢复焦点策略。 |
| Activity/Audit/Plan | header actions 打开 overlay/panel 或 route。 | 打开详情不应重置 Conversation scroll，切换 session/workspace 才重置。 |

---

## 5. 用户体验原则

### 5.1 自动滚动不是无条件滚动

自动滚动只在以下场景发生：

- 用户刚提交输入；
- 用户当前在底部附近；
- 追加内容属于当前用户 submit 触发的 command lifecycle；
- 用户显式点击“回到最新”或类似 affordance。

如果用户已经向上滚动阅读历史，后台事件不应该把用户拉回底部。

### 5.2 焦点恢复优先保护输入连续性

submit 后用户通常希望继续补充指令，或者等待结果。因此：

- 发送成功进入 pending 后，焦点保持在 composer；
- input 暂时 disabled 时，记录 logical focus，恢复 enabled 后再 focus；
- rejected / failed 时保留或恢复 draft，并聚焦 composer；
- ASK card 只有在由当前 submit 直接触发时才可以主动聚焦第一个可回答控件。

### 5.3 不用焦点模拟导航

打开 Activity、Audit、Archived Plan、Task detail 不是输入流的一部分，不应因为这些
面板打开而把 Conversation 滚动或焦点强行移动。

### 5.4 尊重 reduced motion

所有 programmatic scroll 都需要支持 reduced motion。默认可以平滑滚动，但
`prefers-reduced-motion: reduce` 下使用 instant scroll。

---

## 6. Runtime 设计

建议新增：

```text
frontend/src/pages/main-page/runtime/
  mainPageFocusScrollRuntime.ts
  mainPageFocusScrollRuntime.test.ts

frontend/src/pages/main-page/
  useMainPageFocusScrollRuntime.ts
```

`mainPageFocusScrollRuntime.ts` 只包含纯策略和 reducer，不访问 DOM。
`useMainPageFocusScrollRuntime.ts` 负责把策略输出绑定到 refs、scroll container、
input element 和 requestAnimationFrame。

### 6.1 State

```ts
type MainPageFocusScrollRuntimeState = {
  sessionId: string | null;
  workspaceId: string | null;
  messageListSignature: string;
  isPinnedToBottom: boolean;
  userHasManualScrollLock: boolean;
  lastUserScrollAt: string | null;
  pendingSubmitCommandId: string | null;
  pendingFocusRequest: FocusRequest | null;
  pendingScrollRequest: ScrollRequest | null;
};
```

### 6.2 FocusRequest

```ts
type FocusRequest =
  | {
      kind: "composer";
      reason:
        | "submit_started"
        | "command_rejected"
        | "command_failed"
        | "snapshot_reconciled"
        | "input_reenabled";
      commandId: string | null;
    }
  | {
      kind: "ask_card";
      reason: "router_question_created";
      commandId: string | null;
      messageId: string;
    };
```

### 6.3 ScrollRequest

```ts
type ScrollRequest =
  | {
      kind: "bottom";
      behavior: "auto" | "smooth";
      reason:
        | "submit_started"
        | "command_lifecycle_appended"
        | "pinned_activity_appended"
        | "session_changed";
      commandId: string | null;
    }
  | {
      kind: "message";
      behavior: "auto" | "smooth";
      messageId: string;
      reason: "ask_card_focus" | "explicit_open";
    };
```

### 6.4 Actions

```ts
type MainPageFocusScrollRuntimeAction =
  | { type: "runtime.reset_scope"; sessionId: string | null; workspaceId: string | null }
  | { type: "conversation.mounted"; isPinnedToBottom: boolean; messageListSignature: string }
  | { type: "conversation.scrolled"; isPinnedToBottom: boolean; occurredAt: string; source: "user" | "program" }
  | { type: "messages.changed"; messageListSignature: string; appendedMessageIds: string[]; relatedCommandId: string | null }
  | { type: "runtime_input.submit_started"; commandId: string }
  | { type: "runtime_input.command_rejected"; commandId: string }
  | { type: "runtime_input.command_failed"; commandId: string }
  | { type: "runtime_input.command_reconciled"; commandId: string }
  | { type: "router.ask_card_created"; commandId: string | null; messageId: string }
  | { type: "focus.completed" }
  | { type: "scroll.completed"; isPinnedToBottom: boolean };
```

### 6.5 Message signature

不要用整个 message array 做 deep compare。Workbench 可以传入一个轻量 signature：

```ts
const messageListSignature = conversationMessages
  .map((message) => `${message.id}:${message.updatedAt ?? message.occurredAt}`)
  .join("|");
```

如果 `SessionMessageView` 没有 `updatedAt`，第一版只用 `id` 和 `occurredAt`。
新增 message ids 用于判断 append，避免编辑旧 message 时误判为新消息。

---

## 7. Scroll Policy

| 场景 | 行为 |
|---|---|
| 用户 submit | 立即请求 scroll bottom，确保 local user input 和 understanding 可见。 |
| 当前 pinned to bottom，后台追加 answer/activity | 继续 scroll bottom。 |
| 当前 manual scroll lock，后台追加 answer/activity | 不滚动；后续可显示“有新活动” affordance。 |
| 当前 command 的 rejected/failed item 追加 | 即使不在底部，也可以轻量提示；第一版不强制滚动，除非该 command 是当前 submit。 |
| Router ASK card 由当前 submit 触发 | scroll 到 ASK card 并准备 focus request。 |
| 用户手动向上滚动 | 设置 `userHasManualScrollLock=true`。 |
| 用户滚回底部附近 | 清除 manual scroll lock。 |
| 切换 session/workspace | reset runtime，并在首屏 hydration 后定位到最新消息。 |
| 打开 Activity/Audit/Archived Plan/detail panel | 不改变 Conversation scroll。 |

底部判断建议：

```ts
function isNearBottom(element: HTMLElement, thresholdPx = 48): boolean {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= thresholdPx;
}
```

第一版不需要 IntersectionObserver。bottom sentinel 可用于后续更准确地判断，但
`scrollTop` 计算更容易在 JSDOM 中测试。

---

## 8. Focus Policy

| 场景 | 焦点策略 |
|---|---|
| submit started | composer 保持焦点；如果 disabled，记录 composer focus request。 |
| command accepted | 不改变焦点。 |
| snapshot reconciled | 如果 logical focus 在 composer 且 input enabled，恢复 composer focus。 |
| command rejected/failed | 恢复 composer focus，draft 不应被吞掉。 |
| Router ASK card created | 如果 ASK 来自当前 submit，focus 第一个输入控件；否则仅让卡片可 tab 到。 |
| 用户点击 Activity/Audit/Plan | 尊重点击后的浏览器默认焦点，不额外抢焦点。 |
| session/workspace changed | 清空 pending focus request，避免跨 session focus。 |

组件要求：

- composer input 暴露 `ref`；
- ASK card 根节点或第一个回答控件可被定位；
- programmatic focus 使用 `preventScroll: true`，scroll 由 runtime 单独控制；
- focus request 执行后必须 dispatch `focus.completed`，避免重复 focus。

---

## 9. DOM Integration

### 9.1 ConversationLayer

建议扩展为：

```tsx
type ConversationLayerProps = {
  ...
  messageListRef?: Ref<HTMLDivElement>;
  bottomSentinelRef?: Ref<HTMLDivElement>;
  onMessageListScroll?: UIEventHandler<HTMLDivElement>;
};
```

渲染：

```tsx
<div
  className={styles.conversationMessageList}
  onScroll={onMessageListScroll}
  ref={messageListRef}
>
  {messages.map(...)}
  <div aria-hidden="true" ref={bottomSentinelRef} />
</div>
```

### 9.2 MainPageWorkbench

Workbench 作为组合层：

1. 生成 `messageListSignature`；
2. 调用 `useMainPageFocusScrollRuntime`；
3. 把 refs 和 handlers 传给 `ConversationLayer`；
4. 把 input ref 传给 context input；
5. 在 submit lifecycle 调用已有 pending runtime 时，同时 dispatch focus/scroll actions。

Workbench 不直接写复杂 effect。所有判断应放在 runtime policy 或 hook helper 中。

### 9.3 Input composer

当前 input 渲染在 Workbench 内部。建议先做最小改造：

- 添加 `inputRef`；
- submit started 时保留 logical focus；
- disabled -> enabled 后检查 pending composer focus request；
- rejected/failed 后不清空 draft，或通过已有 pending runtime failure path 恢复 draft。

---

## 10. 与 Pending Runtime 的关系

`mainPagePendingRuntime` 负责“显示什么 local item”；
`mainPageFocusScrollRuntime` 负责“用户在哪里、焦点在哪里、是否跟随最新内容”。

两者不互相 import。Workbench 或 hook 组合它们：

```text
submit
  -> pendingRuntime: runtime_input.submit_started
  -> focusScrollRuntime: runtime_input.submit_started
  -> Conversation receives new local messages
  -> focusScrollRuntime: messages.changed
  -> hook executes scroll/focus request after render
```

snapshot hydrate / reconciliation：

```text
snapshot.hydrated
  -> pendingRuntime removes reconciled local items
  -> conversationMessages changes
  -> focusScrollRuntime messages.changed
  -> if pinned or submit-owned, scroll bottom
```

---

## 11. 实现切片

### Slice A: Pure Runtime Policy

- 新增 `mainPageFocusScrollRuntime.ts`。
- 覆盖 reducer tests：
  - submit started creates bottom scroll + composer focus request；
  - pinned append follows bottom；
  - manual scroll lock blocks background append；
  - current command ASK creates message scroll + ask focus request；
  - reset scope clears pending requests。

### Slice B: Conversation DOM Hooks

- `ConversationLayer` 接收 list ref、sentinel ref、scroll handler。
- 新增 `useMainPageFocusScrollRuntime.ts` 执行 scroll/focus request。
- 使用 `requestAnimationFrame` 等待 message DOM render。
- reduced motion 下使用 instant scroll。

### Slice C: Workbench Integration

- Workbench 生成 message signature。
- submit lifecycle 同步 dispatch focus/scroll runtime actions。
- route/session/workspace 改变时 reset runtime。

### Slice D: Composer Focus

- input 暴露 ref。
- submit/rejected/failed/reconciled 后按 policy 恢复 focus。
- component tests 覆盖 focus retention。

### Slice E: ASK Card Focus

- 为 Router ASK message/card 定义可定位 selector 或 ref registry。
- 当前 submit 触发的 ASK card 出现时，scroll 到卡片并 focus 第一个回答控件。
- 不支持自动回答或 focus trap。

### Slice F: Acceptance

- 补充 unit/component tests。
- Electron 验收使用真实 app，而不是 web-only 页面。

---

## 12. 测试计划

### 12.1 Unit Tests

文件：

```text
frontend/src/pages/main-page/runtime/mainPageFocusScrollRuntime.test.ts
```

覆盖：

- submit started；
- pinned append；
- manual scroll lock；
- user returns to bottom；
- ASK card focus request；
- rejected/failed composer focus；
- session/workspace reset。

### 12.2 Component Tests

文件建议：

```text
frontend/src/pages/main-page/mainPageFocusScrollRuntime.test.tsx
```

覆盖：

- local pending item 出现后 scroll container 到底；
- 用户手动 scroll up 后，新 activity 不自动到底；
- rejected 后 input 保持 focus；
- session 切换后 runtime reset。

JSDOM scroll metrics 不可靠的部分使用 helper mock，不把所有判断藏进 DOM。

### 12.3 Electron Acceptance

真实 Electron app 验收：

1. 启动 `npm run electron:dev`。
2. 进入一个有历史 Conversation 的 session。
3. 在底部 submit 一个 read-only Router 问题。
4. 验证 local input 和 understanding 立即可见。
5. 等待 answer，验证仍在底部且 input focus 恢复。
6. 手动向上滚动历史，再提交或触发后台 activity，验证不会被强行拉回。
7. 触发 Router ASK，验证卡片可见且可输入。

---

## 13. 验收标准

1. 用户 submit 后，不等待后端 response 即可看到本地输入和 pending 状态。
2. submit-owned 内容追加后，在用户没有手动阅读历史时自动滚到底部。
3. 用户手动向上滚动后，后台追加不会抢滚动位置。
4. rejected / failed 后，用户输入可恢复，composer focus 明确。
5. Router ASK card 由当前 submit 触发时可见且可回答。
6. 切换 session/workspace 后，focus/scroll runtime 不泄漏旧状态。
7. 设计不修改后端 API，不依赖 snapshot 之外的非正式字段。
8. unit/component tests 覆盖核心 policy；Electron acceptance 覆盖真实 app 交互。

---

## 14. 风险与缓解

| 风险 | 缓解 |
|---|---|
| JSDOM 无法真实模拟 scroll layout | 将判断抽成 pure policy 和 measurement helper，component test 只覆盖集成路径。 |
| 自动 focus 打断屏幕阅读器或键盘用户 | 只对当前 submit 触发的 composer/ASK 做 focus；使用 `preventScroll`；不做 focus trap。 |
| Conversation 内容继续增长导致性能问题 | 本切片不引入虚拟列表，但保留 message signature 和 ref boundary，后续可替换列表实现。 |
| 与 event patch / token streaming 冲突 | runtime 只消费 message signature 和 command lifecycle，不绑定具体数据来源。 |
| 与 archived plan/detail panel 交互混淆 | 明确规定打开 panel 不改变 Conversation scroll；session/workspace 切换才 reset。 |

---

## 15. 下一步

建议从 Slice A 开始实现：

```text
codex/main-page-focus-scroll-runtime
  -> mainPageFocusScrollRuntime.ts
  -> mainPageFocusScrollRuntime.test.ts
```

只有当 pure policy tests 通过后，再进入 ConversationLayer refs 和 Workbench DOM
integration。这样可以避免把不可测试的 scroll/focus 逻辑直接写进大型组件。
