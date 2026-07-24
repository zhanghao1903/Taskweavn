# 会话内原位 ASK 渲染需求

> 状态：F1 需求已确认
>
> 分支：`codex/session-inline-ask-rendering`
>
> 最后更新：2026-07-24
>
> 类型：产品契约 / UX 流程 / Conversation 投影修订
>
> 用户确认：Authoring ASK 与 Execution ASK 均在范围内，D2-D5 采用推荐方案。

## 1. 用户场景

当 Plato 在会话中需要用户补充信息时，用户需要同时看到：

- Plato 原始提出的问题；
- 每个问题的可选项；
- 自己选择了哪个选项，或填写了什么自定义答案；
- 该 ASK 当前处于待回答、提交中、已回答或其他终态。

这些内容应属于同一个会话交互对象。用户完成选择、提交、稍后处理或取消后，
产品应更新原 ASK，而不是在 Conversation 中再创建一个只包含答案的新卡片。

## 2. 当前问题

当前实现与目标存在以下差距：

1. Authoring ASK 的主要交互面位于 Main Work Area；Execution ASK 的主要交互面
   位于 TaskNode Detail Panel。ASK 不在 Conversation 时间线中承担主要交互。
2. Authoring ASK 批量回答后，Conversation 会新增一个 `User answer` 消息，只展示
   已选答案，例如三个答案的编号列表。
3. 新增的答案消息不展示原始问题和候选项，用户回看时无法直接理解答案对应的
   问题与选择范围。
4. Execution ASK 投影保留 `answerId`，但当前 UI 投影不携带可直接渲染的
   `selectedOptionIds` 或回答文本。
5. Conversation 的 `question_card` 协议已能展示问题和选项，但当前选项为只读
   按钮，且协议没有“已选择”“回答文本”“提交中”和完整终态的原位表示。

用户提供的当前界面证据中，Conversation 顶部只出现一张 `Answer / You` 卡片，
内容是三个答案值；原始三个问题和选项已经丢失在会话展示之外。

## 3. 产品目标

### 3.1 核心目标

每次系统 ASK 在 Conversation 中对应一个稳定、持久、可回放的 ASK 卡片。

该卡片：

- 在 ASK 创建时出现在会话时间线的正确位置；
- 在待回答状态下直接承载问题、选项、可选自由文本和提交动作；
- 在用户操作后保留同一个卡片身份和时间线位置；
- 在后端确认回答成功后，将已选项直接标记在原选项中；
- 不为同一次 ASK 回答新增独立的 `User answer` / `Answer` 会话卡片；
- 刷新页面、重启应用或回看历史时仍能恢复完整问答上下文。

### 3.2 “原位更新”的定义

“原位更新”不是仅在视觉上复用相似组件，而是以下产品语义：

- ASK 卡片拥有稳定 `cardId` / ASK 身份；
- `pending -> submitting -> answered` 等状态变化不产生第二个 Conversation 项；
- 卡片的会话排序时间保持为 ASK 创建时间；
- 解决时间作为 `resolvedAt` 或等价事实展示，不改变原始提问位置；
- 用户动作可以继续写入 Activity / Audit 作为证据，但不重复为新的 Conversation
  答案卡片。

### 3.3 选择结果的表现

对于选项型问题：

- 保留所有原始选项；
- 已选择选项使用明确的选中状态；
- 未选择选项保留可读，但在终态下不可操作；
- 不能只依赖颜色表达选中状态；
- 单选、多选和布尔选择分别遵循各自的选择约束。

对于自由文本：

- 回答显示在原问题块内的“你的回答”区域；
- 不新增独立 Conversation 文本消息；
- 选项加补充文本时，两者都显示在同一个问题块中。

对于多问题 Authoring ASK：

- 建议将一次系统澄清交互投影为一张 ASK 组卡片；
- 卡片内按原顺序展示多个问题块；
- 每个问题块分别显示选项、选择结果或自由文本；
- 批量提交只更新这一张组卡片。

此分组方案仍需用户确认，见第 10 节。

## 4. 适用范围

### 4.1 建议的产品契约范围

建议统一适用于两类结构化 ASK：

| ASK 域 | Conversation 表现 | 后端权威 |
|---|---|---|
| Authoring ASK | 会话内 ASK 组卡片，可包含多个问题并批量提交 | RawTask / RawTaskAsk / RawTaskAnswer |
| Execution ASK | 会话内 ASK 卡片，通常对应一个阻塞问题 | AskStore / AskRequest / AskAnswer |

两类 ASK 可以共享会话卡片语义与视觉原语，但必须继续使用各自的命令和后端
权威，不能因为 UI 统一而合并领域生命周期。

### 4.2 建议的首个垂直切片

建议先实现截图直接暴露的 Authoring ASK 批量问答：

1. Conversation 展示原始问题与选项；
2. 用户在该卡片中完成选择；
3. 批量提交后原位显示已选结果；
4. 抑制同一批回答对应的独立 `User answer` Conversation 卡片；
5. 保留原消息、Answer 记录、Activity 和 Audit 事实用于追踪。

Execution ASK 随后复用同一产品契约，避免一次同时改动两个后端权威边界。

## 5. 状态与行为

| 状态 | Conversation 中的要求 |
|---|---|
| loading | 在时间线位置显示 ASK 骨架或加载态，不显示错误答案。 |
| pending | 展示问题、选项、允许的自由文本和主操作。 |
| dirty draft | 保留本地选择，显示未提交状态；切换上下文后按 ASK 身份恢复。 |
| submitting | 保留当前选择，禁用重复提交，显示提交中。 |
| submit failed | 原卡片显示可恢复错误并保留草稿，不标记为已回答。 |
| answered | 原卡片转为只读；已选项和回答文本在原问题中体现。 |
| deferred | 原卡片显示“稍后处理”，保留问题与选项；是否仍可继续回答由后端事实决定。 |
| cancelled | 原卡片只读，显示取消状态和可公开原因。 |
| expired | 原卡片只读，显示已过期；不得提交旧答案。 |
| superseded | Authoring ASK 作为历史保留，显示已被新 Plan/TaskTree 取代。 |
| permission denied | 卡片可读但不可提交，并说明权限原因。 |
| stale / resync | 禁用提交并刷新权威投影，不做乐观已回答。 |

## 6. Conversation、Activity 与 Audit 边界

### Conversation

回答“用户和 Plato 说了什么、问了什么、最终选择了什么”。

- 展示完整 ASK 卡片及其当前权威状态；
- 不为 ASK 选择再创建独立答案卡片；
- 普通只读问答仍可以保留独立的用户问题和 Plato Answer 消息。

### Activity

回答“发生了什么状态变化”。

- 可以保留 `ask_asked`、`ask_answered`、`ask_deferred` 等事件摘要；
- Activity 项不是第二张 Conversation 答案卡片；
- 可以链接到 ASK、Task、Plan 或 Audit。

### Audit

回答“命令、幂等、持久化与恢复是否可信”。

- 保留回答命令、Answer 事实和恢复链路；
- 不因 Conversation 合并展示而删除底层消息或审计证据。

## 7. 数据与权威原则

本节只定义产品要求，不冻结最终 API 结构。

1. Conversation 不得通过解析 `User answer` 文本推断选项状态。
2. Authoring ASK 的问题、选项和答案来自 RawTask 领域事实。
3. Execution ASK 的问题、选项和答案来自 AskStore 领域事实。
4. 提交命令被接受不等于已回答；只有后端投影确认后才能显示 `answered`。
5. 投影必须能表达：
   - ASK 或 ASK 组的稳定身份；
   - 原始问题顺序；
   - 全量选项；
   - 已选择选项；
   - 自由文本答案；
   - 创建时间、解决时间和终态；
   - Authoring / Execution 域；
   - 可执行动作与只读原因。
6. 页面刷新和进程重启后，已回答卡片必须从持久事实恢复，而不是依赖前端缓存。
7. 重放历史时不得重复生成 ASK 卡片和 Answer 卡片。

候选的会话投影语义：

```ts
type ConversationAskCard = {
  cardId: string;
  domain: "authoring" | "execution";
  status:
    | "pending"
    | "submitting"
    | "answered"
    | "deferred"
    | "cancelled"
    | "expired"
    | "superseded";
  createdAt: string;
  resolvedAt?: string | null;
  questions: Array<{
    id: string;
    prompt: string;
    options: Array<{
      id: string;
      label: string;
      description?: string | null;
      selected: boolean;
    }>;
    answerText?: string | null;
  }>;
};
```

该结构仅用于确认产品语义。API Contract 与兼容策略在 F2/F3 后再定稿。

## 8. 非目标

- 不删除普通 Read-only Inquiry 的 Answer 消息。
- 不把 Confirmation 合并为 ASK。
- 不允许编辑已经确认并驱动执行的历史答案。
- 不新增页面、路由、模态流程或独立答案详情页。
- 不在本需求阶段实现附件、图片选项或复杂表单。
- 不以 Conversation 取代 AskStore、RawTask store、Task 状态或 Audit。
- 本轮不修改生产代码、数据库结构或 API。

## 9. 验收标准

1. 系统 ASK 在 Conversation 中展示原始问题和全部选项。
2. 待回答 ASK 可在 Conversation 卡片内完成允许的选择或文本输入。
3. 回答提交中，原卡片保留选择并阻止重复提交。
4. 回答成功后，原卡片以只读方式显示已选项和文本答案。
5. 同一次 ASK 回答不会新增独立 `User answer` / `Answer` Conversation 卡片。
6. 普通 Read-only Inquiry Answer 不受该去重规则影响。
7. Authoring 多问题回答保留问题与答案的一一对应关系。
8. 失败、权限不足、过期、取消、延后、superseded 和 stale 状态均在原卡片表达。
9. 刷新、重启和历史回放后，卡片身份、原始问题、选项和选择结果保持一致。
10. Activity / Audit 继续记录回答动作与恢复证据。
11. ASK 不再在 Conversation 上方、Main Work Area 或 Detail Panel 提供重复的主要
    回答控件；其他区域最多显示状态与跳转入口。
12. 手机、平板和桌面视口均能阅读问题、操作选项并看到终态选择。
13. 键盘和读屏用户可以识别问题、选择状态、提交状态和错误信息。

## 10. 已确认的产品决策

### D1. 领域范围

决定：产品契约与本特性验收覆盖 Authoring ASK 和 Execution ASK。实施可以按
Authoring、Execution 两个垂直切片推进，但两者都必须在同一特性中闭环。

### D2. 多问题分组

决定：一次 Authoring 澄清批次显示为一张 ASK 组卡片，内部包含多个问题块；
不为同一批次的多个问题创建互相分离的会话卡片。

### D3. 其他区域的 ASK

决定：Conversation 成为唯一主要回答面；Main Work Area、Detail Panel、
Top Bar 和 TaskTree 只显示等待状态、任务上下文或“定位到问题”入口，不重复
完整回答控件。

### D4. 自由文本

决定：自由文本显示在原问题块的“你的回答”区域，不生成新的用户消息。

### D5. 历史 `User answer` 消息

决定：Conversation 投影抑制 ASK 专用的独立答案消息，但保留底层消息与
Activity / Audit 证据；普通 Answer 和普通用户输入不受影响。

Activity 中继续显示一条“ASK 已回答”的动作摘要。

## 11. 后续依赖

进入 F2/F3 后需要修订：

- `docs/engineering/ask-lifecycle-contract.md`
- `docs/interaction-model/ask-user-interaction.md`
- `docs/ux/ask-ui-spec.md`
- `docs/plans/ui/session-message-stream.md`
- `docs/plans/feature/session-conversation-activity-timeline.md`
- `docs/plans/feature/router-first-main-input-durable-activity-technical-design.zh-CN.md`
- UI ViewModel / Conversation render protocol
- Authoring 与 Execution ASK 的投影和兼容策略

涉及超过 800 / 1200 行的现有前端文件时，实施前必须运行仓库
Maintainability Gate，并优先把新行为放入有明确边界的 Conversation ASK
组件与投影模块中。
