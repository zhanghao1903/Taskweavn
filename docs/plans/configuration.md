# Plan: 配置系统

> 多 Agent 协作架构 · 配置系统设计计划 · v0 · 2026-05-10

---

## 1. 背景

架构文档反复出现的配置类术语：

```
SessionConfig
  ├─ AutonomyBehavior
  ├─ ConstraintProfile
  ├─ OrchestrationPreset
  └─ interrupt_allowed

AgentTemplate
  ├─ tools
  ├─ capabilities
  └─ system_prompt

ToolMetadata
  ├─ risk_level
  └─ io_scope_hint

PriceTable
Budget / Quota
```

但**这些配置如何定义、加载、合并、版本化、热更新**几乎没说。本 plan 的目标是让配置从"散落各处的概念"变成"可落地的统一系统"。

参考评审：[architecture/review.md](../architecture/review.md) 第 2.2 节（配置系统列为 🟡 低优先空白，但是其他 plan 的依赖项）。

---

## 2. 目标

- **统一**：所有配置走同一套加载 / 验证 / 合并机制
- **分层**：默认 → 用户 → Session → Task 任意层级可覆盖
- **可演进**：schema 版本化，旧 Session 不因新 schema 失效
- **可审计**：每次配置变更产生事件，能追溯
- **类型安全**：Pydantic v2 全程，运行时校验

**非目标：**
- 不做可视化配置编辑器（属于 UX 层）
- 不做远程配置服务（v1 单机）

---

## 3. 待解决的问题清单

| # | 问题 | 难点 |
|---|------|-----|
| 1 | 配置文件格式：YAML / JSON / Python / TOML？ | 用户编辑友好性 vs 表达力 |
| 2 | 配置层级合并的规则？ | 深度合并 vs 替换 |
| 3 | 运行时变更某个配置后，已 running 的任务怎么办？ | 一致性 vs 灵活性 |
| 4 | 哪些配置允许用户编辑，哪些只允许管理员？ | 权限边界 |
| 5 | 配置 schema 演进时旧数据如何迁移？ | 向后兼容 |
| 6 | Agent 模板的注册与发现机制？ | 内置 vs 用户自定义 |

---

## 4. 配置层级模型

```
                        ┌─────────────────┐
                        │  Defaults       │  ← 框架内置
                        │  (built-in)     │
                        └────────┬────────┘
                                 │ 覆盖
                        ┌────────┴────────┐
                        │  User Config    │  ← ~/.codeagent/config.yaml
                        │  (~/.codeagent) │
                        └────────┬────────┘
                                 │ 覆盖
                        ┌────────┴────────┐
                        │  Project Config │  ← <repo>/.codeagent/config.yaml
                        │  (project root) │
                        └────────┬────────┘
                                 │ 覆盖
                        ┌────────┴────────┐
                        │  Session Config │  ← 创建 Session 时传入
                        │  (in-memory)    │
                        └────────┬────────┘
                                 │ 覆盖
                        ┌────────┴────────┐
                        │  Task Config    │  ← 任务级临时覆盖
                        │  (per-task)     │
                        └─────────────────┘

  最终生效配置 = 自顶向下合并（深度合并，下层覆盖上层）
```

**合并规则：**
- 标量字段 → 直接替换
- 列表字段 → 默认替换，可显式 `mode: append` 改为追加
- 字典字段 → 深度合并

---

## 5. 文件格式

**主格式：YAML**（用户友好、注释支持、层级清晰）。

```yaml
# ~/.codeagent/config.yaml
version: "1"

autonomy:
  preset: balanced
  trigger: risky
  wait: block

budget:
  max_usd_per_session: 5.00
  on_exceed: ask_user

constraint_profile:
  preset: code-review
  custom:
    forbid_destructive: true
    require_test_after_fix: true

agent_templates:
  - name: AuditAgent
    capability: audit
    tools: [read_file, search_code, web_search]
    system_prompt_file: prompts/audit.md
```

**辅助格式：Python**（高阶用户用代码生成动态配置）。

```python
from codeagent.config import SessionConfig, ConstraintProfile

config = SessionConfig(
    autonomy=AutonomyBehavior.balanced(),
    constraint_profile=ConstraintProfile.from_preset("code-review"),
    custom_agents=[my_audit_agent],
)
```

---

## 6. 配置 Schema（Pydantic v2）

### 6.1 顶层

```python
class SessionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Literal["1"] = "1"
    autonomy: AutonomyBehavior
    budget: Budget | None = None
    constraint_profile: ConstraintProfile
    orchestration_preset: OrchestrationPreset | None = None
    interrupt_allowed: bool = True
    agent_templates: list[AgentTemplateRef]
    scheduler: SchedulerConfig
    cost_table: CostTableRef = CostTableRef.default()
```

### 6.2 ConstraintProfile

```python
class ConstraintProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset: str | None                          # 引用预设
    forbid_capabilities: list[str] = []         # 禁用某些能力
    require_capabilities: list[str] = []        # 必须包含某些能力
    forbid_tools: list[str] = []
    require_human_for: list[str] = []           # 必须人工确认的动作类
    max_task_depth: int = 5                     # 任务树最大深度
    max_concurrent_tasks: int = 1               # 并发上限（v2）
    max_tasks_per_session: int = 100            # 防爆炸
```

### 6.3 OrchestrationPreset

```python
class OrchestrationPreset(BaseModel):
    name: str
    description: str
    autonomy: AutonomyBehavior
    constraint_profile: ConstraintProfile
    agent_templates: list[str]                  # 预装的 Agent
    initial_workspace: WorkspaceInit | None
```

预设示例：

```yaml
presets:
  code-audit:
    description: "代码审计模式"
    autonomy: { trigger: risky, wait: block }
    constraint_profile:
      forbid_destructive: true
      require_capabilities: [audit, summarize]
    agent_templates: [AuditAgent, FixerAgent, SummaryAgent]

  fast-prototype:
    description: "快速原型模式"
    autonomy: { trigger: destructive, wait: notify }
    constraint_profile:
      max_task_depth: 3
    agent_templates: [CodeGenAgent, TestAgent]
```

---

## 7. 配置加载流程

```
1. 启动时加载 builtin defaults
2. 扫描 ~/.codeagent/config.yaml
3. 扫描当前 cwd 向上找 .codeagent/config.yaml
4. 深度合并三层得到 effective_user_config
5. 用户创建 Session 时传入 SessionConfig（可空）
6. 合并 effective_user_config + session_overrides → final_config
7. Pydantic 校验 → 若失败立即报错并指明哪一层
```

**加载是显式的、有顺序的、可观察的——不依赖隐式环境变量。**

---

## 8. 运行时变更

### 8.1 哪些可变，哪些不可变

```
Session 创建后不可变：
  - constraint_profile.forbid_capabilities    ← 影响已加载的 Agent
  - agent_templates                            ← 改变意味着重启
  - scheduler.mode                             ← 调度器已运行

可热更新：
  - autonomy.trigger / wait                    ← 下一个 ActionCard 立即生效
  - budget.max_usd                             ← 立即重新检查
  - constraint_profile.max_concurrent_tasks    ← 下一次调度生效
  - interrupt_allowed                          ← 立即生效
```

热更新走专门 API：

```python
session.update_config(
    patch={"autonomy": {"trigger": "destructive"}},
)
# 内部：合并 → 校验 → emit ConfigChanged event → 应用
```

### 8.2 配置变更事件

```python
@dataclass(frozen=True)
class ConfigChangedEvent:
    session_id: SessionId
    changed_at: datetime
    diff: ConfigDiff                # 显式 diff，不是新旧全量
    reason: str                     # 用户操作 / 系统降级 / ...
    actor: UserId | "system"
```

写入 EventStream，便于审计"何时、为何、改了什么"。

---

## 9. Schema 版本与迁移

### 9.1 版本字段强制

每个配置文件第一行 `version: "1"` 是必填。

### 9.2 加载时自动迁移

```python
def load_config(path: Path) -> SessionConfig:
    raw = yaml.safe_load(path.read_text())
    version = raw.get("version", "1")
    while version != CURRENT_VERSION:
        raw = MIGRATIONS[version](raw)
        version = raw["version"]
    return SessionConfig.model_validate(raw)
```

迁移函数与代码同仓维护，每次 schema 变更增加一个 `migrate_v{N}_to_v{N+1}`。

### 9.3 已存在 Session 的迁移

老 Session 在 EventStream 中保存了创建时的 SessionConfig 快照。**重启后用快照恢复，不强制升级。** 升级是用户主动行为。

---

## 10. Agent 模板注册

### 10.1 内置模板

```
codeagent/templates/builtin/
  audit_agent.yaml
  fixer_agent.yaml
  summary_agent.yaml
  ...
```

启动时自动扫描注册到 `AgentTemplateRegistry`。

### 10.2 用户自定义模板

```yaml
# ~/.codeagent/templates/my_agent.yaml
name: MyCustomAgent
capability: my_thing
tools: [read_file, write_file]
system_prompt_file: ../prompts/my.md
metadata:
  version: "0.1"
  author: "zhang"
```

启动时也扫描 `~/.codeagent/templates/`。

### 10.3 项目级模板

`<repo>/.codeagent/templates/` 优先级最高（覆盖同名）。

### 10.4 模板版本化

```yaml
metadata:
  version: "0.3.1"
```

Session 中记录使用的模板版本，便于：
- 缓存命中分析（同版本 prompt 才命中）
- 回放调试（按当时版本重放）
- 增量发布（用户可以 pin 到稳定版本）

---

## 11. 权限分层

```
配置项                       管理员    用户    Session 临时
─────────────────────────────────────────────────────
agent_templates 注册         ✓        ✓      ─
quota.max_usd_per_period    ✓        ─      ─
budget.max_usd_per_session   ✓        ✓      ✓
autonomy                     ✓        ✓      ✓
scheduler.mode               ✓        ✓      ✓
constraint_profile           ✓        ✓      ✓
forbid_destructive (强制)    ✓        ─      ─
```

管理员配置走单独命名空间（`/etc/codeagent/admin.yaml` 或类似），不在用户配置层。

---

## 12. 配置验证

### 12.1 静态校验（Pydantic）

类型、必填、范围。

### 12.2 跨字段校验

```python
@model_validator(mode="after")
def check_consistency(self):
    if self.autonomy.wait == "silent" and self.autonomy.trigger == "always":
        raise ValueError("trigger=always with wait=silent is inconsistent")
    if self.budget.on_exceed == "ask_user" and not self.interrupt_allowed:
        raise ValueError("ask_user requires interrupt_allowed=True")
    return self
```

### 12.3 容量校验

```
- agent_templates 中所有 capability 必须可解析
- forbid_capabilities ⊂ 注册的 capabilities
- max_concurrent_tasks ≤ scheduler 支持的上限
```

校验失败必须给出**具体哪一层、哪一行、为何不合法**——不是泛泛的 `ValidationError`。

---

## 13. 待回答的开放问题

| 问题 | 决策需要的输入 |
|------|------------|
| 是否支持配置加密（含 API key 等）？ | 安全要求 |
| 模板的依赖关系怎么表达？ | "FixerAgent 需要 AuditAgent 在同一 Session" |
| 多 Session 共享某些配置（如缓存的 PriceTable）？ | 性能 vs 隔离 |
| Hot-reload 是否监听文件改动？ | 开发体验 vs 运行稳定 |
| 配置的灰度发布（管理员逐步推送给用户）？ | 多租户场景 |

---

## 14. 实施里程碑

```
M1 — 基础 Schema
  ─ SessionConfig / ConstraintProfile / AutonomyBehavior 的 Pydantic 模型
  ─ YAML 加载 + 三层合并
  ─ 静态校验 + 跨字段校验

M2 — 模板注册
  ─ AgentTemplateRegistry
  ─ 内置 + 用户 + 项目三层扫描
  ─ 版本字段

M3 — 运行时变更
  ─ session.update_config API
  ─ ConfigChangedEvent 写 EventStream
  ─ 可变 / 不可变字段区分

M4 — Schema 迁移
  ─ version 字段强制
  ─ 迁移函数框架
  ─ 旧 Session 不被破坏

M5 — 预设系统
  ─ OrchestrationPreset 内置库
  ─ 预设 + 覆盖的合并
  ─ 用户保存自定义预设

M6 — 权限分层
  ─ admin / user / session 三级
  ─ 配置 diff 时的权限检查
```

---

## 15. 验收标准

| 验收点 | 衡量方式 |
|------|---------|
| 三层合并行为可预测 | 单元测试覆盖所有合并规则 |
| 错误的配置给出明确错误 | 错误信息含 file_path + line + reason |
| Schema 演进不破坏旧数据 | 老版本 EventStream 能正常 replay |
| 热更新立即可见 | 改 autonomy 后下一个 ActionCard 用新策略 |
| 模板注册无冲突 | 同名模板按层级覆盖，无歧义 |

---

## 16. 与其他 plan 的关系

- [ux-interaction.md](ux-interaction.md) — AutonomyBehavior 是核心配置项
- [cost-quota.md](cost-quota.md) — Budget / Quota 是配置项
- [observability.md](observability.md) — ConfigChangedEvent 进 EventStream
- [walkthrough.md](walkthrough.md) — 端到端示例需展示配置如何影响调度
- [user-guide.md](user-guide.md) — 用户主要通过配置文件感知系统能力
