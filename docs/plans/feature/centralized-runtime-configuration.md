# Feature Plan: 集中化分级运行时配置系统

> Status: planned
> Type: 新特性支持 / 系统控制面
> Last Updated: 2026-05-13
> Owner/Session: planning session
> Target Implementation Session: independent feature session
> Related Docs: [Configurable Logging System](configurable-logging-system.md), [LLM Provider Plan](llm-provider-retry-thinking.md), [Task-first UI Plan](../task-first-ui-interaction.md), [Planning Workflow](../../planning_workflow.md)

---

## 1. 背景

TaskWeavn 的用户体验很大程度由配置决定：

- 交互频繁度：什么时候问用户，什么时候自动执行；
- 审计强度：哪些 Action 必须审计，审计到什么深度；
- 日志多寡：哪些对象输出日志，输出到哪里，输出多少；
- LLM 行为：provider、model、retry、thinking、routing；
- Task 行为：Task depth、pipeline、agent assignment、result packaging；
- UI 行为：是否显示卡片结果、消息折叠、确认动作样式；
- 安全与预算：风险阈值、成本上限、工具权限。

这些配置目前分散在：

- CLI flags；
- dataclass / Pydantic 默认值；
- 各模块构造参数；
- feature plan 中的未来字段；
- logging / autonomy / LLM provider 等专项计划。

如果继续分散下去，用户体验会变得不可预测：同一个 Session 里为什么这次问用户、为什么这次不问、为什么日志突然很多，很难解释。

本计划目标是把配置升级成 TaskWeavn 的集中化控制面：**分级、可验证、可审计、可热更新**。

---

## 2. 目标

1. 建立统一配置模型：
   - global；
   - workspace/project；
   - session；
   - task；
   - runtime override。
2. 支持配置集中化管理：
   - 统一 schema；
   - 统一加载；
   - 统一合并；
   - 统一校验；
   - 统一变更记录。
3. 支持会话中热更新：
   - logging level / sink；
   - autonomy threshold；
   - audit strength；
   - result packaging policy；
   - LLM retry / provider routing 的下一次请求生效。
4. 定义配置生命周期：
   - 启动加载；
   - 创建 Session；
   - 发布 Task；
   - 运行中 patch；
   - 订阅生效；
   - 归档和 replay。
5. 为 UI / CLI / API 提供配置查询与修改入口。

---

## 3. 非目标

- 不在第一版实现远程配置服务。
- 不做完整权限系统，但预留 user/admin/system scope。
- 不把所有 feature 的详细配置都一次性落地；第一版先做框架和少数高价值配置域。
- 不要求所有配置都能即时热更新；必须区分 live / next_action / next_task / next_session / static。
- 不替代 EventStream / MessageStream。配置变更要记录，但配置本身不是用户消息。

---

## 4. 核心决策

### 4.1 配置是控制面，不是散落参数

模块不应该各自发明配置读取方式。核心模块应依赖：

```text
ConfigStore -> ConfigResolver -> EffectiveConfig -> subscriber/component
```

### 4.2 生效配置是不可变快照

运行时组件读取的是 `EffectiveConfig` 快照，而不是到处读 mutable dict。

热更新时：

```text
ConfigPatch
  -> validate
  -> append ConfigChange
  -> recompute EffectiveConfig
  -> publish ConfigChanged
  -> subscribers apply if hot-updatable
```

### 4.3 不是所有配置都 live 生效

每个配置 key 必须标注 mutability：

| Mutability | 含义 | 示例 |
|---|---|---|
| `live` | 当前运行中立即生效 | logging level、UI presentation density |
| `next_action` | 下一个 Action 决策生效 | autonomy threshold、audit strength |
| `next_llm_call` | 下一次 LLM 请求生效 | retry policy、provider routing |
| `next_task` | 下一个 Task 生效 | tool allowlist、agent assignment policy |
| `next_session` | 下个 Session 生效 | default agent templates |
| `static` | 需要重启或迁移 | workspace root、schema version |

### 4.4 热更新通过 ConfigBus 传播

配置变更不应该靠轮询文件。系统内部使用轻量 `ConfigBus` 发布变更，订阅者按 scope 和 domain 接收。

---

## 5. 配置层级

建议层级：

```text
built-in defaults
  -> user global config        (~/.plato/config.yaml)
  -> workspace config          <workspace>/.plato/config.yaml
  -> session config            workspace/.plato/sessions/<id>/config overlay
  -> task config               task metadata / task config patch
  -> runtime override          UI / CLI / API hot patch
```

合并规则：

| 类型 | 默认规则 |
|---|---|
| scalar | 下层覆盖上层 |
| dict/object | 深度合并 |
| list | 默认整体替换 |
| list with merge mode | 显式 `append` / `remove` / `replace` |
| secret | 不在普通 diff 中显示明文 |

冲突原则：

- scope 越具体优先级越高；
- runtime override 优先级最高，但可设置 TTL；
- system/admin locked key 不能被普通 user override；
- validation 失败时整个 patch 拒绝。

---

## 6. 配置域

第一版建议内置这些 domain：

| Domain | 例子 | Hot Update |
|---|---|---|
| `autonomy` | trigger、risk threshold、wait strategy、timeout action | next_action |
| `audit` | audit mode、sample rate、required actions | next_action |
| `logging` | category level、sink、payload mode | live |
| `llm` | provider、model、retry、thinking、routing | next_llm_call / next_session |
| `task` | max depth、max nodes、default status policy | next_task |
| `pipeline` | task_before / task_begin / task_after | next_task / next_session |
| `result_presentation` | card policy、card density、disable cards | live / next_task |
| `budget` | max cost、token budget、on_exceed | live / next_llm_call |
| `tools` | allowlist、denylist、risk override | next_task |
| `ui` | message density、show raw result、theme hints | live |

第一版不需要把每个 domain 的字段都做完整，但必须让 domain 注册、校验和订阅机制可扩展。

---

## 7. 核心接口草案

### 7.1 ConfigScope

```python
class ConfigScope(BaseModel):
    level: Literal["global", "workspace", "session", "task", "runtime"]
    workspace_id: str | None = None
    session_id: str | None = None
    task_id: str | None = None
```

### 7.2 ConfigPatch

```python
class ConfigPatch(BaseModel):
    patch_id: str
    scope: ConfigScope
    domain: str
    data: dict[str, Any]
    actor: Literal["user", "system", "agent", "api"]
    reason: str | None = None
    ttl_seconds: int | None = None
```

### 7.3 ConfigChange

```python
class ConfigChange(BaseModel):
    change_id: str
    patch: ConfigPatch
    effective_from: datetime
    previous_hash: str
    new_hash: str
    accepted: bool
    validation_errors: list[str] = []
```

### 7.4 EffectiveConfig

```python
class EffectiveConfig(BaseModel):
    config_id: str
    scope: ConfigScope
    version: str
    domains: dict[str, Any]
    source_layers: list[ConfigLayerRef]
    created_at: datetime
```

### 7.5 ConfigStore

```python
class ConfigStore(Protocol):
    def append_patch(self, patch: ConfigPatch) -> ConfigChange:
        ...

    def list_changes(self, scope: ConfigScope) -> list[ConfigChange]:
        ...

    def snapshot(self, scope: ConfigScope) -> EffectiveConfig | None:
        ...
```

### 7.6 ConfigResolver

```python
class ConfigResolver(Protocol):
    def resolve(self, scope: ConfigScope) -> EffectiveConfig:
        ...

    def validate_patch(self, patch: ConfigPatch) -> ValidationResult:
        ...
```

### 7.7 ConfigBus

```python
class ConfigBus(Protocol):
    def publish(self, change: ConfigChange) -> None:
        ...

    def subscribe(
        self,
        *,
        scope: ConfigScope | None = None,
        domains: set[str] | None = None,
    ) -> ConfigSubscription:
        ...
```

---

## 8. 运行时生命周期

### 8.1 启动

```text
load built-in defaults
load user global YAML
load workspace YAML
validate schemas
create global/workspace effective config
```

### 8.2 创建 Session

```text
SessionManager.create(...)
  -> resolve workspace effective config
  -> apply session overrides
  -> persist session config snapshot
  -> publish ConfigLoaded(session)
```

### 8.3 发布 Task

```text
TaskPublisher.publish(...)
  -> resolve session config
  -> apply task-level config patch
  -> validate task constraints
  -> persist task config ref
```

### 8.4 会话中热更新

```text
UI / CLI / API sends ConfigPatch
  -> ConfigStore.append_patch
  -> ConfigResolver validates and recomputes
  -> ConfigBus publishes ConfigChanged
  -> subscribers apply if mutability allows
```

### 8.5 归档和 Replay

每个 Session 归档时应保留：

- session config snapshot；
- config changes；
- task-level config refs；
- rejected config patches；
- config hash timeline。

这样可以回答：

```text
为什么这个 Action 当时需要用户确认？
为什么这个 Task 的日志这么多？
为什么这个 LLM provider 当时用了 DeepSeek thinking？
为什么这个结果被包装成卡片？
```

---

## 9. 用户设置入口

### 9.1 UI

建议三个层级：

| UI Area | Scope | 示例 |
|---|---|---|
| Global Settings | global / workspace | 默认 LLM provider、默认日志 profile |
| Session Controls | session | 本会话 autonomy、audit、logging、result cards |
| Task Advanced Panel | task | 该任务是否强审计、是否包装结果、工具限制 |

### 9.2 CLI

```text
taskweavn config get
taskweavn config set logging.level DEBUG --session <id>
taskweavn config set autonomy.preset careful --session <id>
taskweavn config unset result_presentation.disable_cards --session <id>
taskweavn config history --session <id>
```

### 9.3 配置文件

```yaml
version: "1"

autonomy:
  preset: risk_gated
  threshold: 0.6

logging:
  profile: tester-debug

result_presentation:
  cards:
    enabled: true
    auto_package: true

llm:
  provider: deepseek
  thinking:
    enabled: true
```

---

## 10. 与日志系统的关系

可配置日志系统是这个配置层的第一个重度消费者。

日志系统不应该自己实现一套继承和热更新机制；它应该：

1. 注册 `logging` domain schema；
2. 订阅 `ConfigBus(domain=logging)`；
3. 收到 live patch 后原子替换 handler / level / sink；
4. 在 LogContext 中记录 config hash。

这样日志计划可以专注于日志事件、sink、归档和输出格式，而不是重复造配置合并系统。

---

## 11. 执行切片

### Slice 1: Config Schema Registry

- `ConfigDomain`
- `ConfigScope`
- `ConfigPatch`
- `ConfigChange`
- `EffectiveConfig`
- mutability metadata

### Slice 2: Config Resolver

- built-in defaults；
- YAML load；
- layer merge；
- validation；
- effective config hash。

### Slice 3: Config Store

- SQLite `config_changes`；
- SQLite `config_snapshots`；
- rejected patch record；
- session/task scope queries。

### Slice 4: ConfigBus

- in-process publish/subscribe；
- domain filtering；
- scope filtering；
- subscriber lifecycle。

### Slice 5: First Consumers

- logging live level update；
- autonomy next_action threshold update；
- result_presentation live disable/enable；
- LLM retry/policy next call config ref。

### Slice 6: UI / CLI API

- config get/set/unset/history；
- session settings API；
- task advanced config API；
- validation error display。

### Slice 7: Replay And Docs

- config timeline in session archive；
- replay helper；
- user guide；
- migration note from old flags/defaults。

---

## 12. 验收标准

1. 同一配置 key 可以在 global / workspace / session / task 层覆盖，最终值正确。
2. 无效 patch 被拒绝，并记录 validation error。
3. `logging.level` 在运行中更新后立即影响输出。
4. `autonomy.threshold` 更新后从下一个 Action 决策开始生效。
5. task-level tool/audit override 不影响其他 Task。
6. 配置变更能在 Session 归档中被查询。
7. UI/CLI 可以看到 effective config 和变更历史。
8. 现有模块默认值可以平滑迁移到 built-in defaults。

---

## 13. 风险

| Risk | Mitigation |
|---|---|
| 配置系统过度抽象 | 第一版只落地高价值 domain 和少量消费者 |
| 热更新导致运行中状态不一致 | 每个 key 标注 mutability；不能 live 的延迟到边界生效 |
| 配置来源难以解释 | EffectiveConfig 保留 source_layers 和 hash |
| UI 暴露太多选项 | UI 使用 profile + advanced panel，不直接暴露全量 schema |
| 日志 / autonomy 各自重复实现配置 | 明确由 centralized config 提供合并和订阅 |

---

## 14. Open Questions

1. 是否需要单独的 `workspace_id`，还是 workspace path 足够？
2. runtime override 是否默认带 TTL？
3. user/global config 存放路径是否固定为 `~/.plato/config.yaml`？
4. secret 是否进入同一配置系统，还是单独 SecretStore？
5. UI 是否允许编辑 task-level 配置，还是第一版只读展示？

---

## 15. Status

- Status: planned
- Next Step: 在独立实现会话中先做 Slice 1 + Slice 2，并让 logging plan 依赖该配置解析层。
