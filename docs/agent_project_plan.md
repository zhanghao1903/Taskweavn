# Agent 项目计划（Markdown 版）

## 优先级说明
- 🔴 P0：必做  
- 🟠 P1：重要  
- 🟢 P2：增强  
- ⚪ P3：未来  

# Tier 1 — 设计理念

## 架构线（系统设计原则）
### Action / Observation 对称
所有操作是强类型 Action，所有反馈是对称的 Observation。CodeAction 是 Action 的子类，不破坏类型系统。

### Runtime 解耦
Agent 核心不知道执行环境（本地 / Docker / 远程沙箱）。接口统一，执行透明。

### 单 Agent 优先，多 Agent 预埋
先完成单 Agent，多 Agent 作为上层抽象。

### Thought 旁路存储
Thought 不作为 EventStream 一等成员，通过 event_id 关联。

## 执行线（工程原则）
### 可配置优先于硬编码
非核心能力全部配置化。

### 接口先于实现
先定义 Protocol。

### 可观测性内置
日志 / replay / 查询从一开始支持。

### 审计不依赖 LLM 自觉
tracking 强制声明，自动插桩。

# Tier 2 — 总体规划

## 架构线（A）
- A1 🔴 核心抽象层（Week 1–2）
- A2 🟠 CodeAction + 审计（Week 3–4）
- A3 🟢 多 Agent 架构（Week 7–8）
- A4 🟢 经验与评估体系（Week 9–10）

## 执行线（E）
- E1 🔴 最小单 Agent（Week 1–3）
- E2 🟠 CodeAction + 审计（Week 4–6）
- E3 🟠 记忆 + RAG（Week 6–8）
- E4 🟢 多 Agent 编排（Week 9–12）

# Tier 3 — 详细规划

## Phase 1（Week 1–3）
- Action / Observation
- EventStream
- LLMClient
- Tools
- ReAct 循环

## Phase 2（Week 4–6）
- CodeAction
- 沙箱执行
- 审计 Agent
- ThoughtStore

## Phase 3（Week 6–8）
- ConversationHistory
- RAG
- 持久化
- Benchmark

## Phase 4（Week 9–12）
- 多 Agent
- 可观测性
- 推理优化
