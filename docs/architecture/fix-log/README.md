# README.md 事实校准记录

> 校准对象：`docs/architecture/README.md`
>
> 原文保留：`docs/architecture/archive/original/README.original.md`
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
| 校准前 source revision | `e64ca969364eb711f72d808b22f787697e2723d1` |
| Source blob | `1312b2fe3b7d16834e2859090524e54f23d7d20b` |
| 原文最后修改 commit | `9170d04aada11775bae9a1cf43a70edaef411ab8` |
| 原文最后修改 date | `2026-06-24T00:53:35+08:00` |
| 原文最后修改 subject | `Align architecture docs with Product 1.1` |

`README.original.md` 在改写前复制。终审必须证明它与
`e64ca969364eb711f72d808b22f787697e2723d1:docs/architecture/README.md`
byte-for-byte 一致。单篇旧 fix log 中的“HEAD”可能表示校准时工作树核对，或该
文件最后修改 commit/blob；这些都是 point-in-time 记录，不应解释成当前 PR HEAD，
也不替代本文件以 `e64ca969...` 为统一基准的 manifest。

---

## 2. 校准输入

README 在全部非索引文档完成后最后处理。输入不是旧索引中的分类，而是：

1. 顶层 Markdown 实际文件清单；
2. `fix-log/` 实际文件清单；
3. 23 篇非 README active 文档的 status、purpose 和 current/non-current 结论；
4. 23 篇 original 的存在与校准前 source revision/blob hash；
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
matching archive/original/<stem>.original.md
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
- 每个 original 与固定的校准前 source revision 对应 active file 一致；
- 每个 manifest Git blob/SHA-256 与 preserved original 一致；
- 每个 current active 与 original 有实质差异。

结果：

- active = 24；
- originals = 24；
- fix logs = 24；
- 三组 basename sets 完全一致；
- 24 份 original 均与
  `e64ca969364eb711f72d808b22f787697e2723d1:docs/architecture/<name>.md`
  byte-for-byte 一致；
- 24 项 manifest Git blob/SHA-256 均与 preserved original 一致；
- 24 份 current active 均与 corresponding original 不同；
- central manifest 不把会随后续修订失效的 current-active SHA 当作持久校验条件；
  单篇旧日志中保留的 point-in-time current SHA 仅作为历史验证记录。

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
| `docs/architecture/archive/original/README.original.md` | 保留 2026-06-24 原索引 |
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

---

## 10. Required CI Follow-Up

2026-07-11 更新 active README 的验证日期和 CI 事实：

- `.github/workflows/required-ci.yml` 现在对每个 PR 运行完整 backend tests、
  frontend test/lint/build 和 sidecar E2E，并提供 `Required CI Gate` 聚合结果；
- GitHub 对当前私有仓库的 `main` branch-protection API 返回套餐限制 403；
- 因此 workflow coverage 已补齐，但 merge-blocking required enforcement 仍需
  GitHub Pro 或 public repository 条件。

---

## 11. 完整 original provenance manifest

24 份 original 的统一校准前 source revision 是
`e64ca969364eb711f72d808b22f787697e2723d1`，即 architecture calibration commit
`21735738832dbc22f4e86658ef62d937ccd8ba66` 的直接父提交。下表把每个 source
path 的 Git blob 与 preserved original 的 SHA-256 固定下来；单篇 fix log 可以重复
这些值，但不再要求 24 份日志各自维护一份容易漂移的不完整清单。

| Active document | Source Git blob | Preserved original SHA-256 |
|---|---|---|
| `README.md` | `1312b2fe3b7d16834e2859090524e54f23d7d20b` | `5a1592c9c6cd6f6f4a67950e8679c0997414527bda9a1075a64a2f2cadcc1be7` |
| `agent.md` | `00a54f1321247a762b974e6fc5c7c53e3a81f7b7` | `e5ae76438606a7d92d99eab5864103d653df0ae3fb6e99f4838742842f5d28bd` |
| `authoring-command-protocol.md` | `93f7829cf4fadf9859b366a2909925579485f788` | `191858b0e2486e6e87e00125de2c1cf73bafdae9957110c25e43a73e58b2b026` |
| `authoring-domain.md` | `0c8f4faf03ff8fe759f6c9a8e8d3ec04a37615b6` | `6011f7a1a097f8580ebf0beaa823663c9007e9ffad75050fa464d33e6bea72d0` |
| `bus-v2.md` | `2e125f752362ed6ccc901b9699c5ae8b8e921029` | `3c20f16080970ecf9f895e44b79abcc9d156cffcb0ef6f640e56c42f06f0a01f` |
| `bus.md` | `93ce04aa45e1008089fdcb1ae279aa82cc0003f6` | `3f0608e9ac5769b3b610ccc748609a87994a0d0ba951a73885dce2ed7cd6f640` |
| `collaborator-agent-task-authoring.md` | `0d431327f095ec570fc64976ad8723aa5ec2e3f2` | `e85b3641142d7a0c603a6bfbb5bc71b1c7f8eaec36b09a62137f0a240ccc7d29` |
| `configurable-logging-system.md` | `622793bf5b033bcc0995353a85ef5568490b8895` | `57e719d7d0bc02b350f790f0440c5ce8a100e4a5fa2a2fa1565c86e415ce3db2` |
| `context-manager.md` | `c7a648d93253263c5972e5f178448bb78a31bd86` | `70ff8a76551bfb3dbaa3dd540a58863418c62dadecff0d278eed7c88d2cf9ab4` |
| `contract-revision-and-execution-loops.md` | `74f2f93ed96a86f4f1dd58fbeb52c5c498398486` | `f108493107364bdcdc2f42b10e5515b2d5c874641c5ecb6a3f00442b698cfeb2` |
| `interaction-layer.md` | `65c5ffb0316d28b611cb0a9cc053d12ebaafcb17` | `b36329784a333ca3b673225a57c86b9d199d4244664edac6b8920392bc47d7c0` |
| `llm-provider-reliability.md` | `68e0fd16a7e0ee4702b7892aadff97e46ba251c7` | `a7ef8369956b85f5edb1afb598579eaffccb07d79d1880b369644c41f790cf9b` |
| `multi-agent-collaboration.md` | `46b6bf5afe84b93c92998b8a5c3aec18b68ac2b9` | `34dcf7b869c955b8fc3b6b5e574b4812912cde7dcf5cf5ae5d43b9a2688c00a3` |
| `multi-agent-collaboration_en.md` | `c7c260077cf03f04c1b99901e2a1fa432b2bbb82` | `c4f1794d571d1fee1eca615845fdee3020d2ed6293c0cefa24a319f8f4c4c42d` |
| `overview.md` | `14de4a882a1d1f61d5da00bef48528d808b05793` | `2bba6b324b80a9e02903cbaf5195c114a1a12aa6ec26634b447e8c929b1fd349` |
| `reference.md` | `e0b793e919365dd4d3df61aaf61d934cf3ecadd7` | `a2b03154ea52383c8321b1c1b092ed536e4bf2ce935f096cbc1a288c16cef765` |
| `review.md` | `2958e6603fa35609ca9deaace8da26ee910c7d72` | `aac022452892dd26a5f639f86d6bb3ec9c787832db3794654da607165aee980e` |
| `session.md` | `9a5808822cde35931603085d400f87dfe0f41002` | `755b88258a338d16c7edb79198b3d9bdc75f5e9aaed56e628e5503e0ee3a45df` |
| `task-domain-ui-model-separation.md` | `4b5f5311bf26f10153076d7c32f2efdab02454c1` | `3623584e8b260f9c927325e1dc687c25f41f9c0ff0efa80a50098bd74390467c` |
| `task.md` | `f4880df74307963f01c3b0079326429cf1ccb771` | `e1d996eaa14ca120bd6c225b73f2c9c68522d1382fc0b1c3699fd8951e5fc1d8` |
| `taskbus-service-multi-execution-env.md` | `97698222d139faa3d54848a28065097064daa8c5` | `d1f85440a53631a1c629bba8de2b05a6379ae4589b46cab5ba0bd78f6c76f9a0` |
| `tool-capability-layer.md` | `453b49949572c57cc029321e93b1219a742af693` | `57059959522b7bfefc7beac2f18d9908b20d852ec0b3fbf8bb472b09a0cc894c` |
| `ui-backend-communication.md` | `8330eac219dca47f2d8d580268193a788839851f` | `8881b6aa7b43357ac41a6e223ae603ff558248e05d8155fb6a60d79ea4c75a21` |
| `workspace-communication-protocol.md` | `5b568d16540992ed63d2c465779db0d34216402d` | `aaf7dbdc587e73e84563dbbf2e1f9042be09b00bb449aee8093ea4529a36519b` |

复现要求：

- `git rev-parse <source-revision>:docs/architecture/<name>.md` 必须等于表中
  source blob；
- `git diff --quiet <source-revision>:docs/architecture/<name>.md
  HEAD:docs/architecture/archive/original/<name>.original.md` 必须成功；
- preserved original 的 `shasum -a 256` 必须等于表中 SHA-256。

---

## 12. PR #182 Review Follow-Up

2026-07-11 的合并前审查修正了三类事实问题：

1. active `authoring-domain.md` / `overview.md` 不再把不存在的 `TaskClaim`、
   `TaskFailure` 写成当前实现对象；
2. original provenance 从含糊的 current `HEAD` / 易失效 current-file SHA 改为
   固定 source revision、Git blob 和 SHA-256 manifest；
3. active `review.md` 的证据清单改为当前 `.github/workflows/required-ci.yml`。

这次 follow-up 不修改任何 original，也不改变生产代码、测试行为或架构评分。
