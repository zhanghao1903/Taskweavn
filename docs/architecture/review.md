# 当前架构评审与事实基线

> Status: fact-calibrated architecture review
> Last Updated: 2026-07-10
> Original historical review:
> `docs/architecture/review.original.md`
> Verification record:
> [fix-log/review.md](fix-log/review.md)
> Scope: local-first Product 1.1 architecture, implementation closure,
> reliability, trust boundaries, validation, and deferred extension paths.

## 1. 评审方法

本文把两类内容分开：

- **事实**：必须能由代码、测试、release evidence、ADR 或已校准架构文档证明；
- **评价**：分数和优先级不是事实，必须公开评价标准和推导依据。

本次不再评价“新颖性”。旧文档把尚未实现的 `CreateTaskTool`、LLM scheduler、
IOScope/bus-v2 和 constraint-driven Agent graph 当作架构亮点，这种评分无法反映当前
系统质量。

当前评审标准：

1. authority 是否单一且可追溯；
2. 本地端到端产品路径是否闭环；
3. failure/retry/recovery 是否收敛；
4. tool、workspace、secret 和 external input 是否有可执行的安全边界；
5. logs/events/audit/diagnostics 是否可用且不过度暴露；
6. LLM/context/usage/config 是否可观察、可控制；
7. tests、CI、packaging 是否形成发布门禁；
8. future design 是否与 current implementation 明确分开。

## 2. 结论摘要

当前架构已经从早期概念稿发展为一个真实的 local-first Product 1.1 闭环：

```text
Main Page input
  -> Runtime Input Router
  -> inquiry / guidance / interaction resolution / execution handoff
  -> command-backed Plan / Task facts
  -> TaskBus
  -> fixed-route Default Agent
  -> workspace tools + Context Manager + LLM
  -> durable conversation / activity / audit / diagnostics / usage
```

最强的部分：

- authority 和 command/query 边界已经形成；
- authoring、Published Task、execution、interaction、context、UI projection 有真实
  store/service/test；
- 本地 sidecar、React frontend、Electron packaging 和 restart replay 有验证资产；
- 未来 multi-Agent、remote ExecutionEnv 和 unified workspace protocol 已被明确标成
  future，不再伪装成现状。

最需要优先处理的部分：

1. ASK/confirmation 与 TaskBus 的跨 store 一致性和 recovery 不对称；
2. Default Agent 的 direct write/shell 能力尚无统一 permission/policy enforcement；
3. raw LLM/log payload 的敏感信息边界不足；
4. LLM timeout/fallback/circuit/failed-usage evidence 不完整；
5. 大量本地测试没有对应的完整 CI gate；
6. legacy/new contracts 和多套 projection/status 仍增加认知与恢复复杂度。

**评价结论**：当前适合 local macOS technical evaluation 和受控使用；还不能据此
宣称 distributed、multi-Agent、security-hardened 或 broad-consumer production
readiness。

## 3. 主要发现

### 3.1 High: Interaction 与 Task lifecycle 跨库一致性

当前 execution ASK 和 confirmation 都跨越独立 stores：

```text
ASK:          AskStore <-> TaskBus
confirmation: MessageStream <-> TaskBus
```

已验证事实：

- ASK create + Task wait 不是一个事务；
- ASK answer 先持久化，再尝试 Task resume 和 dispatch；
- ASK 有 `DefaultAskRecoveryService` 做 snapshot/startup 补偿；
- confirmation response 先写 MessageStream，再尝试 Task resume；
- confirmation 没有与 ASK 对等的 recovery service；
- direct confirmation HTTP route 不请求 execution dispatch；
- response value 不校验是否属于 action options；
- MessageStream schema 允许一个 actionable 保留多个不同 response，读侧选择最早一条；
- `pending_actionable` 不检查 `requires_response`。

架构风险：

- 用户已回答，但 Task 仍停在 waiting 或恢复到 pending 后不自动继续；
- UI、MessageStream 和 TaskBus 对“是否已解决”产生短暂或持久分歧；
- process crash 后 ASK 可补偿，confirmation 没有同等级收敛路径。

建议：先建立 interaction resolution command/outbox 或显式 convergence record，再统一
ASK/confirmation recovery 和 dispatch semantics。不要仅在 HTTP handler 中继续增加
best-effort 调用。

### 3.2 High: Tool 权限与执行隔离仍是局部策略

当前 Main Page Default Agent 可直接装配：

- workspace read/write/append/replace；
- workspace search/list；
- `run_command`；
- optional web retrieval；
- optional computer-use；
- ASK/confirmation。

现有保护：

- `Workspace.resolve()` 拒绝 root 外路径和 `.plato`/legacy metadata；
- precision mutations 有 content-hash/line-range guard；
- computer-use 和 web tools 由 settings 控制；
- WeChat send runtime 强制 high risk + human confirmation；
- Context Manager 给 LLM 提供 allowed-tool guidance。

当前缺口：

- Workspace path policy 不是 OS sandbox；
- `RunCommandTool` 的 cwd 是 workspace，但 command 本身不是通用 permission sandbox；
- 没有统一 `ToolAccessPolicy`、per-Agent permission profile 或 runtime enforcement
  chain；
- authoring capability catalog 与实际 execution Tool inventory 不是同一个动态 source；
- Execution Plane `CapabilityPolicy` 的 generic path 主要匹配 required capability 和
  allowed-tools subset；`denied_tools`、risk、runtime/token limits、callback policy 未被
  generic service 全面执行；
- local Task API 不是 external multi-tenant auth boundary。

架构风险：能力描述、LLM guidance 和实际可执行权限可能漂移。建议将 tool identity、
workspace scope、risk、confirmation 和 execution limit 汇聚到运行时可强制的 policy
decision，而不是只存在于 prompt、DTO 或静态 catalog。

### 3.3 High: Raw LLM 与日志 payload 的敏感信息边界不足

当前可观察性很强，但 raw archive 不是默认可分享材料：

- `llm_io` 在 INFO 记录完整 prompts、tools、output 和 reasoning；
- LoggingManager 的 `summary` / `full` payload mode 不自动变换 producer payload；
- key-based redaction 不扫描任意字符串，也不处理 message/context；
- `main_page_trace` 和 frontend error logger 不经过 LoggingManager redactor；
- provider retry error summary 可包含 exception text；
- diagnostic bundle 有更强 secondary sanitizer，但不会反向清理原始 log files。

架构风险：本地 prompt、workspace content、absolute paths、tool arguments 或 secrets
进入 raw logs。建议默认降低 `llm_io` 暴露、让 payload mode 成为 producer contract，
并对 message/context/error strings 增加结构化 sanitizer。诊断导出应继续使用 allowlist
和引用，而不是复制 raw archive。

### 3.4 Medium-High: LLM failure resilience 和 usage evidence 不完整

已实现：

- provider-neutral ChatRequest/ChatResponse；
- typed error classification；
- bounded retry/backoff/jitter；
- DeepSeek/OpenRouter/LiteLLM providers；
- role-aware model profiles；
- token usage ledger 和 UI summaries。

限制：

- 默认 180 秒 provider timeout 失败只尝试一次；
- 没有 TaskWeavn-level cross-provider fallback、circuit breaker、health pool 或 automatic
  model downgrade；
- final failed attempt 不生成 RetryRecord；
- SDK internal retries 对上层不可见；
- usage ledger 只在成功返回 ChatResponse 后写入，不记录 failed call/retry attempt；
- injected shared LLM 会绕过 per-role profile selection；
- Main Page 当前只装配四个 role clients，audit/summary role 尚未进入该 assembly；
- provider 参数支持矩阵不一致。

建议：先补 failed-attempt evidence、timeout policy 和 secret-safe error mapping，再决定
是否需要 fallback/circuit。Fallback 必须有 side-effect/idempotency 约束，不能只在
provider 层盲目重放。

### 3.5 Medium: 多 store 与 compatibility contract 增加收敛成本

当前 durable stores 分工清楚，但边界数量多：

- Session registry；
- authoring / Plan；
- TaskBus；
- ASK；
- MessageStream；
- EventStream；
- Context；
- result/error summaries；
- UI events；
- usage；
- runtime config；
- Execution Plane。

当前 compatibility 还包括：

- durable `Plan/PlanTaskNode` 与 legacy `DraftTaskTree`；
- `PlanView.task_nodes` 与 compatibility `task_tree_projection`；
- core Session status 与 Main Page UI status projection；
- Authoring ASK、Execution ASK、confirmation 三套交互 authority；
- EventStream、MessageStream、Activity 和 UI event 四类时间线/增量事实；
- static authoring capabilities 与 concrete execution tools。

这不是“应该合并成一个数据库”的结论。风险在于跨 authority command 没有统一
convergence/idempotency/recovery pattern。建议先建立 store ownership matrix、command
commit order 和 recovery invariant，再按 usage evidence 移除 legacy projections。

### 3.6 Medium: 当前串行路径不能自动推广为并发安全

当前 Main Page fixed-route dispatcher 使用一个 worker，按 queue drain Session，通常
提供一个 writer lane。但：

- TaskBus 本身不禁止同一 Session 同时 claim 多个 eligible Tasks；
- SQLite TaskBus claim lock 是 instance-local；
- 没有 distributed lease、heartbeat、fencing 或 stale worker reclaim；
- 多个 Session 当前共享同一个 workspace project root；
- 没有 multi-writer branch/merge/conflict protocol。

对当前单 sidecar fixed-route scope，这些是明确限制而不是立即故障。任何增加 worker、
remote env 或 dynamic Agent 的工作，都必须先把这些隐含串行假设变成显式协议。

### 3.7 Medium: 测试资产强，但 CI gate 明显窄于测试资产

2026-07-10 的静态/collection evidence：

- 141 个顶层 backend `test_*.py` 文件；
- `pytest --collect-only` 收集 1520 个 tests；
- 69 个 `frontend/src` 下的 `.test.ts/.test.tsx` 文件；
- 5 个 sidecar-backed frontend E2E test files；
- 多个 Electron dev/packaged/installer/launcher/restart smoke scripts；
- release notes 记录了 DMG verify 和 installer smoke。

GitHub Actions 当前只有一个 workflow：

```text
Product 1.0 Frontend Integration
  -> path-filtered PR/main runs
  -> npm run test:e2e:sidecar
  -> two local sidecar fixtures
  -> five frontend E2E files
```

它不等于完整 backend pytest、frontend unit tests、ESLint、TypeScript/Vite build、Ruff、
Mypy、packaging smoke 的统一 PR gate。

本次校准首次运行完整 suites，证明“有测试资产”和“未经验证就假定 baseline 全绿”
不是同一件事。当时发现：

- backend：`1507 passed, 10 skipped, 3 failed`；三项定向复跑仍失败；
  - 两项 read-only inquiry sidecar acceptance 把期望的 `answered` 路由成
    `dispatched`；
  - Main Page snapshot canonical fixture 与当前模型 dump 不一致；
- frontend：`557 passed, 6 skipped, 1 failed`；失败的 resync transient-state test
  定向复跑通过，表现为 full-suite 时序不稳定。

这些失败不是文档变更造成的。事实校准提交 `2173573` 完成后，同日按上述顺序完成
follow-up：

- read-only inquiry acceptance 与共享 sidecar fixture 中后来加入的 pending ASK 隔离，
  保留 active ASK 优先级这一既有 Router 语义；
- canonical snapshot fixture 补齐当前模型已经序列化的 `archivedAt`、
  `archivedPlans` 和 `conversationRender` 字段；
- resync test 用测试控制的 pending refetch 取代固定 `80ms` 观察窗口；
- backend 完整复跑为 `1510 passed, 10 skipped`；
- frontend 完整复跑为 `558 passed, 6 skipped`；
- sidecar E2E 在允许子进程读取既有 uv cache 后为 `5 files passed, 6 tests passed`；
- frontend lint 为 0 errors、2 个既有 Fast Refresh warnings，build 通过并保留既有
  chunk-size warning。

因此 2026-07-10 的这些已知 baseline failures 已收敛，但完整 CI gate 仍未覆盖上述
完整矩阵。后续重点是把这些 suites 变成持续 required checks，而不是只增加更多测试
文件。

建议至少建立：

1. backend unit/integration-with-skips；
2. frontend unit + lint + build；
3. sidecar E2E；
4. macOS-only Electron/package smoke；
5. optional credentialed provider/Desktop smoke。

### 3.8 Medium: Cost 可见性已落地，预算/配额仍未执行

当前 token usage：

- 记录成功 ChatResponse 的 provider/model/token/cache metadata；
- 可按 task/plan/session/workspace 聚合；
- Main Page 在 1,000,000 reported tokens 以上显示固定 high-usage warning。

当前没有：

- user/session/task budget model；
- USD price table/cost event；
- preflight/mid-flight budget enforcement；
- provider call hard quota；
- Execution Plane `max_llm_tokens` 的 generic enforcement；
- failed/retried attempt usage accounting。

因此“成本可观察”是当前事实，“成本可控制”不是。

### 3.9 Conditional: Public distribution hardening

正式 Product 1.1 release evidence 记录：

- local macOS Apple Silicon；
- unsigned DMG；
- not notarized；
- not hosted SaaS；
- no auto-update/public marketplace/remote execution claim。

如果目标仍是受控 technical evaluation，这些是明确 scope。如果目标变为 broad public
distribution，signing、notarization、update、crash/support telemetry、compatibility
matrix 和 release CI 会成为高优先级依赖。

## 4. 当前架构优势

### 4.1 Authority 分工已经真实落地

| Fact | Authority |
|---|---|
| RawTask / Plan / TaskNode | authoring and Plan stores/commands |
| Published Task lifecycle | TaskBus |
| execution ASK | AskStore + TaskBus linkage |
| confirmation message/response | MessageStream + TaskBus linkage |
| execution trace | EventStream |
| LLM input context | Context Manager / ContextStore |
| result/error summary | TaskExecutionSummaryStore |
| UI replay cursor | UiEventStore |
| token usage | usage ledger |
| service Task execution | Execution Plane store + TaskBus |

Router、Collaborator、Agent、UI 和 logs 都不能直接替代这些 authority。

### 4.2 本地 vertical slice 完整

当前真实闭环包括：

- router-first input；
- command-backed authoring/revision；
- explicit Plan publish；
- fixed-route execution；
- precision file and shell tools；
- ASK/confirmation；
- cooperative stop/retry；
- result/error/file-change projection；
- Conversation/Activity/Audit/diagnostics；
- workspace inspection；
- token usage；
- Electron packaging and restart replay evidence。

这比旧评审的“设计成熟、实现稀薄”状态有实质变化。

### 4.3 Error 和 recovery 已有共享语言

`ProductErrorCategory`、`ProductRecoveryAction`、API error mapping、LLM classification
mapping、Task failure metadata、frontend normalization 和 recovery labels 已实现并有测试。

TaskBus 支持 failed Task 原 identity retry，ASK 有 recovery，interrupted running Task 有
startup recovery，Execution Plane publish 有 idempotency records。虽然不完整，但不再是
旧评审所说的“failed + 新建任务”模型。

### 4.4 Trust surfaces 比旧评审完整

当前有：

- typed EventStream；
- structured logs and archives；
- Audit Page projections；
- sanitized payload disclosure；
- diagnostic bundle；
- workspace file/diff evidence；
- result/error summaries；
- product error refs；
- usage summaries。

这些 trust surfaces 有各自 authority，并未错误地把 logs 当作产品事实。

### 4.5 Future/current 边界已改善

已接受但未实现的 dynamic routing、Agent Manager、remote worker lease、unified
WorkspaceRequest、Tool marketplace、MCP、multi-writer merge 等现在能在 calibrated
docs 中明确识别。这个边界比“先画完整未来系统，再用 header 说尚未实现”更可靠。

## 5. 历史评审结论的当前状态

| 2026-05-09 项目 | 2026-07-10 事实 |
|---|---|
| `CreateTaskTool` 是核心创新 | 当前不存在 generic CreateTaskTool；任务创建走 Collaborator/Authoring/Contract Revision/Publisher commands |
| constraint-driven Agent graph | `ConstraintProfile`、OrchestrationDesigner、graph editor 均未实现 |
| bus-v2 IOScope 解决并发 | IOScope/ConflictGuard 仍是 target design；当前 fixed-route 串行 |
| LLM scheduler + rationale | dynamic assignment/Routing Agent 未实现；Runtime Input Router 不是 Task scheduler |
| error/retry 是明显空白 | product taxonomy、Task retry、LLM retry、recovery 已部分落地；跨 store/fallback 仍有缺口 |
| security/permission 完全空白 | workspace protection、settings gates、confirmation、computer-use policy 已有；统一 permission enforcement 仍缺 |
| observability 完全空白 | structured logging、Event/Audit/diagnostics/usage 已落地；privacy/process-global limits 仍在 |
| HITL/UX 未设计 | 三类 ASK/confirmation UI 与 Router input 已落地；语义统一/原子性仍缺 |
| cost/quota 空白 | token usage visibility 已落地；budget/quota enforcement 未落地 |
| storage 形态不清 | 多个 concrete SQLite stores 已落地；cross-store transaction/recovery 成为新问题 |
| config system 未设计 | Settings、runtime config、Agent LLM、logging config 已落地；consumer coverage 不完整，旧 orchestration config 未实现 |
| capability pending 可永久卡住 | fixed-route claim 使用 Task capability；无 compatible env 时 Execution Plane 明确拒绝；dynamic routing stale sweep 仍 future |
| test strategy 空白 | backend/frontend/E2E/smoke 资产丰富；CI coverage 仍不足 |
| 缺端到端 trace | overview、release evidence、sidecar E2E 已提供真实路径；文档仍可增加一个逐事实 walkthrough |

## 6. 评价分数

以下是评价，不是代码事实。

| 维度 | 分数 | 权重 | 依据 |
|---|---:|---:|---|
| Authority / domain boundaries | 8 | 20% | store/command/query ownership 清楚，但交互与 compatibility authority 仍多 |
| Local end-to-end closure | 8 | 20% | Product 1.1 本地闭环、Electron 和 restart replay 成立 |
| Reliability / recovery | 6 | 15% | 多项 recovery 已有；confirmation、cross-store、LLM fallback 仍弱 |
| Security / privacy / isolation | 5 | 15% | path/settings/confirmation 有基础；permission enforcement、shell isolation、raw logs 不足 |
| Observability / audit / diagnostics | 7 | 10% | surface 丰富；redaction/payload/process-global 限制明显 |
| LLM / context / cost governance | 6 | 10% | provider/context/usage 已落地；failure evidence、budget、consumer coverage 不完整 |
| Tests / CI / release confidence | 7 | 10% | 测试资产和 smoke 强；CI matrix、signing/notarization 不完整 |
| **加权总分** | **6.9 / 10** | 100% | local technical product 成立，production hardening 尚未闭合 |

旧评审的 `6.7 -> 7.3` 不能与此分数直接比较：评价维度已经从“新颖性/完整性/直观性”
改为当前 implementation risk。

## 7. 推荐路线

### P0: 先收敛现有闭环

1. **Interaction convergence**
   - confirmation recovery；
   - resolve + resume + dispatch 的统一 command/outbox；
   - response uniqueness/options validation；
   - ASK/confirmation shared projection semantics。
2. **Execution permission and secret boundary**
   - runtime-enforced Tool policy；
   - shell/computer-use scope；
   - Execution Plane policy enforcement matrix；
   - `llm_io`/message/context/error sanitizer。
3. **CI baseline**
   - backend full tests；
   - frontend test/lint/build；
   - existing sidecar E2E；
   - required checks on PR。

### P1: 降低故障和迁移成本

4. **LLM failed-attempt evidence and resilience**
   - timeout policy；
   - failed usage/retry telemetry；
   - secret-safe provider errors；
   - explicit fallback/circuit decision。
5. **Contract convergence**
   - Plan/TaskNode migration exit criteria；
   - legacy DraftTaskTree removal sequence；
   - one status ownership matrix；
   - timeline/event source responsibilities。
6. **Control-plane enforcement**
   - runtime config consumer coverage；
   - token budget/quota model；
   - Execution Plane generic policy enforcement；
   - multi-workspace logging isolation。

### P2: 只在产品需求成立后扩展

7. Dynamic assignment / Agent Manager。
8. Remote ExecutionEnv registration/lease/heartbeat。
9. Parallel workspace writer isolation/merge。
10. Unified workspace/tool provider protocol、MCP 或 marketplace。
11. Signed/notarized/update-enabled public distribution。

这些 extension 不应先于 P0/P1，因为它们会放大当前 cross-store、permission、logging
和 CI 风险。

## 8. 验证证据

本评审使用：

- `docs/architecture/` 当前 calibrated documents 和 fix logs；
- `src/taskweavn/` authority/assembly/store/runtime code；
- `frontend/src/` API contracts、Main Page、Settings、Audit 和 E2E；
- 20 个 accepted/historical ADR；
- Product 1.1 formal/beta release evidence；
- `.github/workflows/product-1-0-frontend-integration.yml`；
- `frontend/package.json` scripts；
- backend/frontend test inventory and current test runs。

评审更新时，应先更新事实证据，再更新评分。评分不能反向决定事实。
