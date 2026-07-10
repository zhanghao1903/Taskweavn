# README.md 事实校准记录

> 校准对象：`docs/architecture/README.md`
>
> 原文保留：`docs/architecture/README.original.md`
>
> 校准日期：2026-07-10
>
> 校准范围：architecture 索引、文档状态、阅读路径和三联文件完整性

---

## 1. 原文保全

| 项目 | 值 |
|---|---|
| 原文行数 | 100 |
| 原文 SHA-256 | `5a1592c9c6cd6f6f4a67950e8679c0997414527bda9a1075a64a2f2cadcc1be7` |
| HEAD commit | `9170d04aada11775bae9a1cf43a70edaef411ab8` |
| HEAD blob | `1312b2fe3b7d16834e2859090524e54f23d7d20b` |
| HEAD date | `2026-06-24T00:53:35+08:00` |
| HEAD subject | `Align architecture docs with Product 1.1` |

`README.original.md` 在改写前复制。终审必须证明它与
`HEAD:docs/architecture/README.md` byte-for-byte 一致。

---

## 2. 校准输入

README 在全部非索引文档完成后最后处理。输入不是旧索引中的分类，而是：

1. 顶层 Markdown 实际文件清单；
2. `fix-log/` 实际文件清单；
3. 23 篇非 README active 文档的 status、purpose 和 current/non-current 结论；
4. 23 篇 original 的存在与 HEAD hash；
5. 23 篇 fix log 的事实、纠正与验证记录；
6. 当前代码中已落地的 embedded Execution Plane、fixed-route runtime、
   Runtime Input、Plan、Activity、multi-workspace 等事实；
7. `review.md` 记录的完整测试基线和已知验证限制。

开始校准时的计数：

~~~text
24 top-level active documents, including README
23 preserved originals
23 fix logs
~~~

完成 README 三联文件后，目标计数是 `24 / 24 / 24`。

---

## 3. 旧索引的主要问题

### 3.1 状态分类已经失真

旧 README 把以下文档合并标为“Historical substrate / review input”：

- `reference.md`；
- `interaction-layer.md`；
- `multi-agent-collaboration.md`；
- `multi-agent-collaboration_en.md`；
- `review.md`。

逐篇校准后，它们的当前角色分别是：

- current implementation reference；
- current interaction fact document；
- current multi-Agent absence/extension boundary（中英文）；
- current architecture risk/evaluation snapshot。

original 文件才是 historical substrate。

### 3.2 Execution Plane 被写成纯未来方向

旧 README 将 `taskbus-service-multi-execution-env.md` 描述成
“not the default Product 1.1 local loop”的 exploratory direction。

当前代码和已校准文档证明已存在：

- service-level Task DTO；
- `EmbeddedTaskApiService`；
- local HTTP shell；
- `SqliteExecutionPlaneStore`；
- local ExecutionEnv registry；
- selected local runtime handlers；
- ordinary TaskRequest 到 TaskBus/dispatcher 的 embedded path。

remote registration、distributed lease/heartbeat 和 separated service 仍是 future。
新索引必须同时表达两边。

### 3.3 Session ownership 表述过强

旧 matrix 写“Session owns ... settings-derived runtime”。

当前事实是：

- Session 是 product continuity 和 fact namespace；
- `MainPageWorkspaceRuntime` owns stores/services/default agent/dispatcher；
-多个 Session共享 workspace root；
- public identity 是 workspace + Session。

新索引改为具体的 identity、registry、store scope、runtime 和 recovery 边界。

### 3.4 没有校准 provenance

旧索引没有说明：

- active/current 文档如何识别；
- original 如何使用；
- fix log 的位置与作用；
- original 不应被同步更新；
- future/current 冲突如何判定；
-逐篇校准和验证流程。

因此读者无法判断“旧稿”“现稿”“修复依据”之间的关系。

### 3.5 阅读顺序过度扁平

旧 README 把 13 篇列为所有 non-trivial work 的统一 must-read。该规则没有根据
任务类型和 blast radius 区分。

新索引提供：

-最小架构定向；
-按 Task/authoring/UI/tool/LLM/Execution Plane/multi-Agent/review 的阅读路径；
-按变更范围扩展阅读，而不是机械读取全部文档。

---

## 4. 逐项修复

| 旧索引陈述 | 判定 | 修复 |
|---|---|---|
| Last Updated 2026-06-24 | 过期 | 更新为 2026-07-10 完整校准状态 |
| “Most files required; a few older files retained” | 分类不清 | 定义 active/original/fix-log 三类 |
| reference 是 historical substrate | 错误 | 标为 current substrate/assembly reference |
| interaction-layer 是 historical substrate | 错误 | 标为 current interaction fact |
| multi-Agent docs 是 design lineage | 错误 | 标为 current absence + extension boundary |
| review 是历史 input | 错误 | 标为 current risk/evaluation snapshot |
| Execution Plane memo 只是未来方向 | 不完整 | current embedded facts + future distributed service |
| Session owns runtime | 错误 | workspace runtime owns；Session提供 continuity/scope |
| bus-v2 是普通 area doc | 容易误用 | 明确 future design reference / not current runtime |
| workspace protocol “full protocol not implemented” | 过粗 | 分开 implemented inspection/precision slices 与 future unified protocol |
| 一个统一 must-read list | 低效 | 改为最小定向 + task-specific paths |
| 没有 complete catalog | 缺失 | 24 篇 active 文档全部入表 |
| 没有 original links | 缺失 | 每篇列 original |
| 没有 fix-log links | 缺失 | 每篇列 calibration log |
| 没有 conflict priority | 缺失 | 增加 source/test/architecture/contract/product/ADR/original 顺序 |
| 没有维护流程 | 缺失 | 增加逐篇核验、保全、修复、验证和最后更新索引 |
| “完成校准”容易被理解为全套测试全绿 | 风险 | 回链 review fix log 的已知基线失败和验证限制 |

---

## 5. 完整目录核验

新 README 必须覆盖以下 24 篇 active 文档：

### 5.1 Index、map 与 review

1. `README.md`
2. `overview.md`
3. `reference.md`
4. `session.md`
5. `review.md`

### 5.2 Execution

6. `task.md`
7. `bus.md`
8. `agent.md`
9. `taskbus-service-multi-execution-env.md`
10. `bus-v2.md`

### 5.3 Authoring

11. `authoring-domain.md`
12. `authoring-command-protocol.md`
13. `collaborator-agent-task-authoring.md`
14. `contract-revision-and-execution-loops.md`

### 5.4 Interaction/UI

15. `interaction-layer.md`
16. `task-domain-ui-model-separation.md`
17. `ui-backend-communication.md`

### 5.5 Context/tool/workspace

18. `context-manager.md`
19. `tool-capability-layer.md`
20. `workspace-communication-protocol.md`

### 5.6 Reliability/observability

21. `llm-provider-reliability.md`
22. `configurable-logging-system.md`

### 5.7 Multi-Agent

23. `multi-agent-collaboration.md`
24. `multi-agent-collaboration_en.md`

每一项必须同时存在：

~~~text
active document
matching <stem>.original.md
matching fix-log/<basename>.md
~~~

---

## 6. 新索引的事实规则

### 6.1 Active 的含义

active 表示“仍参与当前架构判断”，不表示全文都是 implemented。例如
`bus-v2.md` 作为 active future memo 的当前事实是“这些 v2 能力尚不存在，
以下内容是 future design”。

### 6.2 Current 与 future 可以同篇存在

以下文档有明确双边界：

- `taskbus-service-multi-execution-env.md`；
- `workspace-communication-protocol.md`；
- `tool-capability-layer.md`；
- `agent.md`；
- `task.md`；
- `bus.md`。

索引描述必须同时指出 implemented slice 和 future boundary。

### 6.3 双语文档不是自动镜像

`multi-agent-collaboration.md` 与
`multi-agent-collaboration_en.md` 分别核验，结论一致但结构和细节可不同。

### 6.4 Review 的性质

`review.md`：

- facts 必须有证据；
- score/priority 是公开标准下的评价；
-不是第二套 runtime authority；
-包含当前 full-suite/CI/release 风险。

---

## 7. 验证计划

### 7.1 File triads

验证：

- active count = 24；
- original count = 24；
- fix-log count = 24；
- basename sets 完全相等；
-每个 original SHA 与对应 `HEAD` active file 一致；
-每个 current active 与 original 有实质差异。

结果：

- active = 24；
- originals = 24；
- fix logs = 24；
-三组 basename sets 完全一致；
- 24 份 original SHA-256 均与对应
  `HEAD:docs/architecture/<name>.md` 一致；
- 24 份 current active 均与 corresponding original 不同；
- README current SHA-256 =
  `cadad8270b2c6ba2e9b45d56dafdd28a98052b62afedf635a98921ef800f46ce`。

状态：通过。

### 7.2 Links 与 Markdown

验证：

-所有 active architecture 文档的 local Markdown links；
-所有 fix logs 的 local Markdown links；
- README catalog 的 72 个 current/original/log links；
- fence 配对；
- placeholder/temporary marker；
- `git diff --check`。

结果：

-扫描 24 份 active documents 和 24 份 fix logs；
-在忽略 fenced code 与 inline code 后检查 372 个 local Markdown links；
- README catalog row set 与 24 个 active basenames 完全一致；
- 48 份文件的 backtick/tilde fence parity 通过；
-全部 active 文档包含 2026-07-10 calibration date；
-无临时 placeholder；
- `git diff --check -- docs/architecture` 通过。

状态：通过。

### 7.3 Scope

验证：

-本轮 README 只新增/修改三个索引 artifacts；
-整个 architecture 校准没有修改 `src/`、`frontend/src/` 或
  `tests/`；
-用户已有工作树变化保持不动。

结果：

- `git status --short src frontend/src tests` 无输出；
- architecture 变化只包含本目标的 active/original/fix-log artifacts；
-既有 `AGENTS.md` 修改和
  `docs/product/plato-1-1-feature-test-report-2026-07-02.md` 未跟踪文件保持
  原样；
-当前分支仍为 `codex/architecture-fact-calibration`；
-无 staged files。

状态：通过。

### 7.4 Code tests

README 只重建索引，不增加新的实现陈述，因此不重复运行完整代码测试。各主题的
定向验证位于各自 fix log；最近完成的 Session calibration 运行了：

~~~text
backend:  254 passed in 20.86s
frontend: 33 passed across 4 files in 1.56s
~~~

完整测试基线仍以 `fix-log/review.md` 为准。该记录保留校准时发现的失败，并补充了
同日按顺序修复后的 backend、frontend、sidecar E2E、lint 和 build 复跑结果。

---

## 8. 变更文件

| 文件 | 处理 |
|---|---|
| `docs/architecture/README.original.md` | 保留 2026-06-24 原索引 |
| `docs/architecture/README.md` | 重建为 24 篇 active 文档的事实索引 |
| `docs/architecture/fix-log/README.md` | 新增校准依据和完整性检查 |

未修改任何代码、测试、product contract、ADR 或 release 文档。

---

## 9. 校准结论

新 README 不再维护一份“current docs vs historical substrate”的人工印象列表。
它以可验证三联结构表达：

~~~text
current explanation -> active document
before state        -> original document
reason/evidence     -> fix log
~~~

同时，它把唯一纯 future runtime memo `bus-v2.md` 明确标出，并对
Execution Plane、workspace protocol、tool capability、Agent/Task/Bus 文档采用
“implemented facts + explicit extension boundary”的准确分类。
