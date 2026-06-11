# Precision File Tools Technical Design

> Status: completed for Product 1.1 precision file tools scope
>
> Last Updated: 2026-06-11
>
> Related Plan: [Precision File Tools](precision-file-tools.md)
>
> Product Baseline:
> [Workspace-Aware Agent Foundation](../../product/plato-1-1-workspace-aware-agent-foundation.md)
>
> Predecessor:
> [Product 1.1 Workspace Inspection Milestone](product-1-1-workspace-inspection-milestone.md)
>
> Existing Contract:
> [Git, Diff, And File Viewer API Contract](../../engineering/git-diff-file-viewer-api-contract.md)

---

## 1. 设计目标

Precision File Tools 的目标是把当前粗粒度 `read_file` / `write_file`
能力升级为更适合代码任务的安全工具层：

```text
read_file_range
search_workspace
replace_file_range
append_file
  -> durable operation evidence
  -> changed-line projection
  -> Main / Audit / Outcome / Diagnostics
```

这不是一个编辑器方案，也不是完整 Git 客户端方案。它只解决 Product
1.1 中最关键的文件操作风险：

- Agent 不应该为了改几行而重写整个文件；
- Agent 不应该在文件已经变化后继续覆盖旧上下文；
- append 重试不应该重复写入；
- 用户和 Audit 不应该只看到 Agent prose，而要看到结构化 changed-line
  evidence。

## 2. 当前基础

现有可复用基础：

| 现有模块 | 可复用能力 |
|---|---|
| `src/taskweavn/workspace_inspection/path_policy.py` | workspace-relative path、`.plato` 保护、路径穿越保护、safe path label。 |
| `src/taskweavn/workspace_inspection/gateway.py` | WorkspaceInspectionGateway 编排入口。 |
| `src/taskweavn/workspace_inspection/store.py` | inspection evidence SQLite store，可扩展 evidence kind。 |
| `src/taskweavn/workspace_inspection/git_provider.py` | git status / structured diff / text file content read。 |
| `src/taskweavn/server/ui_http_inspection.py` | workspace-scoped HTTP inspection route adapter。 |
| `src/taskweavn/tools/fs.py` | 当前 read/write/list 基础工具，后续可保留兼容。 |
| `src/taskweavn/task/event_file_changes.py` | observed file facts 到 file summary 的投影入口。 |

当前不足：

1. `ReadFileTool` 是全文件读取，没有 line range 和内容大小治理。
2. `WriteFileTool` 是全文件覆盖，不支持 expected hash / drift guard。
3. 没有 workspace search 工具。
4. 没有 mutating file operation idempotency store。
5. changed-line evidence 不是文件工具的一等输出。

## 3. 模块边界

建议新增 backend 模块：

```text
src/taskweavn/workspace_inspection/precision_files.py
src/taskweavn/workspace_inspection/precision_store.py
src/taskweavn/tools/precision_fs.py
```

可选 HTTP debug / future UI 模块：

```text
src/taskweavn/server/ui_http_precision_files.py
```

初期不建议暴露直接 UI 写接口。第一版写操作主要给 execution Agent tool
adapter 使用。UI 侧通过现有 Workspace Inspection / Audit 查看结果。

## 4. 数据模型

### 4.1 Line Range

```python
class WorkspaceLineRange(BaseModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
```

规则：

- 1-based line number；
- `start_line <= end_line`；
- first slice 不支持 zero-length insertion；
- 插入语义后续单独设计，避免把 replace 语义做得过宽。

### 4.2 Text Line

```python
class WorkspaceTextLine(BaseModel):
    line_number: int
    text: str
    truncated: bool = False
```

### 4.3 Read Range Response

```python
class ReadFileRangeResponse(BaseModel):
    schema_version: Literal["plato.precision_file.read_range.v1"]
    workspace_id: str
    file: WorkspacePathRefView
    range: WorkspaceLineRangeView
    lines: list[WorkspaceTextLine]
    content_hash: WorkspaceContentHash
    range_hash: WorkspaceContentHash
    warnings: list[WorkspaceInspectionWarning] = []
```

`content_hash` 是整文件 hash，用于后续 drift check。`range_hash` 是当前
range 的 hash，用于 UI / Audit 精确说明。

### 4.4 Search Request / Response

第一版只做 literal search 和 filename search。regex 与 semantic search
后置。

```python
class SearchWorkspaceRequest(BaseModel):
    query: str
    mode: Literal["literal", "filename"] = "literal"
    case_sensitive: bool = False
    include_globs: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    max_files: int = 50
    max_matches: int = 200
```

```python
class WorkspaceSearchMatch(BaseModel):
    file: WorkspacePathRefView
    line_number: int | None
    preview: str
    match_start: int | None = None
    match_end: int | None = None
```

### 4.5 Replace Request / Response

```python
class ReplaceFileRangeRequest(BaseModel):
    operation_id: str
    path: str
    start_line: int
    end_line: int
    replacement_text: str
    expected_content_hash: WorkspaceContentHash
    reason: Literal["task_execution", "user_command", "recovery"]
```

```python
class ReplaceFileRangeResponse(BaseModel):
    schema_version: Literal["plato.precision_file.replace_range.v1"]
    operation_id: str
    workspace_id: str
    file: WorkspacePathRefView
    changed_line_ranges: list[WorkspaceLineRangeView]
    before_hash: WorkspaceContentHash
    after_hash: WorkspaceContentHash
    bytes_written: int
    evidence_ref: WorkspaceInspectionEvidenceRef
    replayed: bool = False
```

### 4.6 Append Request / Response

```python
class AppendFileRequest(BaseModel):
    operation_id: str
    path: str
    content: str
    expected_content_hash: WorkspaceContentHash
    ensure_trailing_newline: bool = True
    reason: Literal["task_execution", "user_command", "recovery"]
```

第一版默认只 append 已存在 text file。`create_if_missing` 暂不开放，避免
append 与 create/write 的权限语义混在一起。

## 5. 换行与文本策略

第一版只支持 UTF-8 text file。

规则：

1. 读取时识别 dominant newline：`\n`、`\r\n`、`\r`。
2. 写回时保留 dominant newline。
3. replacement / append 输入内部可使用 `\n`，写回时转换成 dominant
   newline。
4. 如果文件没有 final newline，append 时根据
   `ensure_trailing_newline=True` 先补换行再追加。
5. 单行超过上限时拒绝写入或返回 validation error，不做静默截断写。

## 6. Drift Guard

Mutating tools 必须先读取当前文件 hash：

```text
current_hash = sha256(current_file_bytes)
if current_hash != expected_content_hash:
  reject workspace.file_drift
```

错误形状：

```python
class PrecisionFileToolError(BaseModel):
    code: Literal[
        "workspace.file_drift",
        "workspace.path_rejected",
        "workspace.file_missing",
        "workspace.file_too_large",
        "workspace.binary_unsupported",
        "workspace.operation_conflict",
        "workspace.range_invalid",
    ]
    message: str
    retryable: bool
    recovery_actions: tuple[str, ...]
```

`workspace.file_drift` 的 recovery action：

- `refresh_file`;
- `inspect_diff`;
- `retry_with_latest_context`;
- `ask_user` if autonomy requires user decision.

## 7. Mutating Operation Idempotency

必须新增 operation store，避免 append 在 LLM/provider/network retry 后重复写。

建议存储在现有 inspection DB：

```text
<workspace>/.plato/inspection.sqlite

precision_file_operations
  operation_id TEXT PRIMARY KEY
  request_hash TEXT NOT NULL
  kind TEXT NOT NULL
  workspace_id TEXT NOT NULL
  path_label TEXT NOT NULL
  status TEXT NOT NULL
  before_hash TEXT
  after_hash TEXT
  evidence_id TEXT
  response_json TEXT
  created_at TEXT NOT NULL
  completed_at TEXT
```

规则：

1. 同一 `operation_id + request_hash`：
   - 如果已完成，返回 stored response，`replayed=True`；
   - 如果执行中，返回 conflict / busy，避免并发写。
2. 同一 `operation_id` 但 request hash 不同：
   - reject `workspace.operation_conflict`。
3. 写文件与记录 response 必须尽量在一个 service transaction 边界内完成。
   文件系统写无法真正 SQLite 原子化，因此顺序应为：

```text
reserve operation
read current file and validate hash
write temp file
atomic replace target
capture evidence / response
mark completed
```

append 也应该走 temp file + atomic replace，而不是直接 append handle。

## 8. Provider 流程

### 8.1 Read File Range

```text
resolve path
reject protected / binary / too large
read bytes
decode UTF-8
split lines with line numbers
slice requested range
compute full content hash + range hash
return bounded lines
```

### 8.2 Search Workspace

```text
resolve search root = workspace root
walk allowed files
skip .plato / binary / too large / hidden policy exclusions
apply include/exclude globs
literal filename or text search
return bounded matches with safe path labels
```

后续可替换成 ripgrep provider，但第一版应避免 shell 拼接用户输入。如果使用
`rg`，必须固定 args list，并关闭任意 shell 字符串拼接。

### 8.3 Replace File Range

```text
reserve operation_id
resolve path
read current bytes
validate expected_content_hash
decode text and split line records
validate start/end
replace selected range
write temp file
atomic replace
compute after_hash
capture evidence
record operation response
emit observation
```

### 8.4 Append File

```text
reserve operation_id
resolve path
read current bytes
validate expected_content_hash
normalize newline
append content
write temp file
atomic replace
compute changed line range
capture evidence
record operation response
emit observation
```

## 9. Evidence Model

建议扩展 `WorkspaceInspectionEvidenceRef.kind`：

```ts
type PrecisionFileEvidenceKind =
  | "file_range_read_snapshot"
  | "workspace_search_snapshot"
  | "line_replace_snapshot"
  | "append_snapshot";
```

Evidence descriptor：

```json
{
  "kind": "line_replace_snapshot",
  "operationId": "op_...",
  "pathLabel": "workspace://ws/src/App.tsx",
  "beforeHash": {"algorithm": "sha256", "value": "..."},
  "afterHash": {"algorithm": "sha256", "value": "..."},
  "changedLineRanges": [{"startLine": 12, "endLine": 18}],
  "truncated": false
}
```

Audit / Diagnostics / Result Summary 只能消费 descriptor 和 evidence ref，
不要复制完整文件内容。

## 10. Tool Adapter

新增 `src/taskweavn/tools/precision_fs.py`：

```text
ReadFileRangeTool
SearchWorkspaceTool
ReplaceFileRangeTool
AppendFileTool
```

Tool metadata：

| Tool | Pool | effect_target | risk |
|---|---|---|---:|
| `read_file_range` | `workspace.basic` | `read_only` | low |
| `search_workspace` | `workspace.basic` | `read_only` | low/medium |
| `replace_file_range` | `workspace.basic` | `user_workspace` | medium/high |
| `append_file` | `workspace.basic` | `user_workspace` | medium |

Mutating tools should expose enough schema hints so LLM learns the correct
sequence:

```text
read/search first -> inspect hash/line numbers -> replace/append with expected hash
```

## 11. Risk / Confirmation

Initial risk policy：

| Condition | Suggested risk |
|---|---:|
| read/search | low |
| replace <= 20 lines in known source/doc file with matching hash | medium |
| append <= 100 lines with matching hash | medium |
| config/lock/security file | high |
| no expected hash | reject by default |
| generated/binary/large file | reject or high if later allowed |
| many files / many lines | high / confirmation required |

如果 autonomy profile 要求确认，高风险写操作应进入现有 confirmation
lifecycle，而不是绕开 UI。

## 12. Projection

Precision tool observation 应进入现有 observed file fact / file summary
通道：

```text
PrecisionFileObservation
  -> EventStream / MessageStream process note
  -> task file facts
  -> MainPageSnapshot.fileChangeSummary
  -> AuditRecord evidence refs
  -> Diagnostic bundle descriptors
```

投影规则：

- `changedLineRanges` 优先来自 precision operation evidence；
- 如果缺失，退回到 structured diff hunks；
- 如果两者都缺失，只显示 file-level summary；
- Agent prose 不作为 changed-line source of truth。

## 13. API 边界

第一版不要求新增用户可直接调用的 HTTP write API。

如果需要 API，应使用 workspace-scoped service route，并默认 service-only：

```http
POST /api/v1/workspaces/{workspaceId}/precision-files/read-range
POST /api/v1/workspaces/{workspaceId}/precision-files/search
POST /api/v1/workspaces/{workspaceId}/precision-files/replace-range
POST /api/v1/workspaces/{workspaceId}/precision-files/append
```

Renderer UI 不应直接暴露 replace/append，除非后续有明确的用户编辑
interaction design。

## 14. Test Plan

### Backend Unit

- path normalization and `.plato` rejection;
- symlink escape rejection;
- UTF-8 read range;
- CJK line range and search;
- oversized file fallback;
- binary file fallback;
- literal filename search;
- literal text search;
- search max file/match truncation;
- replace success;
- replace invalid range;
- replace drift rejection;
- append success;
- append final newline behavior;
- append idempotent replay;
- operation id conflict;
- evidence descriptor redaction.

### Tool / Agent Integration

- tool schema validates expected hash;
- read/search observations are read-only;
- replace/append observations include evidence refs;
- drift rejection produces recoverable task-visible error;
- high-risk file replacement can route to confirmation when policy requires.

### Projection / UI

- file summary shows changed line ranges when available;
- Audit detail shows evidence ref and path label;
- diagnostics export includes redacted precision operation descriptor;
- existing Workspace Inspection file/diff viewer still opens the target file.

### Smoke

1. Seed workspace with git repo and known text file.
2. Use Agent/tool path to read lines.
3. Replace one line range with matching hash.
4. Append one block with stable operation id.
5. Re-run same append operation id and confirm no duplicate content.
6. Inspect Main Page file summary, Audit evidence, and Workspace Inspection diff.

## 15. Implementation Order

Recommended slices:

1. Model + limits + warning/error codes.
2. Read range + search provider.
3. Operation store.
4. Replace provider.
5. Append provider.
6. Tool adapters.
7. Projection/Audit/diagnostic wiring.
8. Sidecar/Electron smoke.

Do not wire LLM-visible mutating tools before idempotency and drift tests pass.

## 16. Implementation Status

`codex/precision-file-tools` implements the first backend/tool foundation:

- `src/taskweavn/workspace_inspection/precision_files.py` provides bounded
  `read_file_range`, `search_workspace`, `replace_file_range`, and
  `append_file` service behavior.
- `src/taskweavn/workspace_inspection/precision_store.py` stores durable
  mutation operation idempotency records in `.plato/inspection.sqlite`.
- `src/taskweavn/tools/precision_fs.py` exposes LLM-visible tool adapters with
  drift-guarded mutation observations.
- `src/taskweavn/server/main_page_agent.py` and `src/taskweavn/cli/main.py`
  register the precision tools beside the legacy file tools.
- `src/taskweavn/task/event_file_changes.py` projects precision mutation
  observations into deterministic task file summaries with changed line ranges
  and evidence refs.
- `tests/test_precision_file_tools.py` and
  `tests/test_task_event_file_changes.py` cover the core read/search/mutation
  and projection behavior.

Explicitly not implemented in this slice:

- direct renderer write API;
- frontend file editor controls;
- full Audit Page detail UI for precision evidence;
- diagnostics export formatting dedicated to precision operation descriptors;
- high-risk pattern policy beyond existing baseline tool risk metadata.

## 17. Blockers / Open Decisions

1. Whether zero-length insertion is required in Product 1.1 first slice.
2. Whether literal-only search is sufficient for the first user path.
3. Whether direct UI write controls should remain out of scope.
4. Whether high-risk file patterns should be centralized in autonomy/risk config
   before the first mutating tool ships.
