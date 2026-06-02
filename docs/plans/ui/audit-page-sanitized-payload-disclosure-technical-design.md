# Audit Page Sanitized Payload Disclosure Technical Design

> Status: draft technical design
> Last Updated: 2026-05-31
> Scope: Audit Page sanitized payload disclosure for record detail and evidence
> detail.
> Related:
> [Audit Page Contract](../../engineering/audit-page-contract.md),
> [Audit Page Implementation Plan](audit-page-project-implementation-plan.md),
> [Audit Page Readiness Notes](audit-page-readiness-notes.md)

---

## 1. Problem

Audit Page 已经能展示产品化的审计记录，并且后端第一版已经能从
Task projection、EventStream、session log archive、logging config manifest
中生成记录。

下一步用户会自然追问：

```text
这条审计记录背后的具体证据是什么？
系统为什么说它被确认、被跳过、失败、部分可见或存在风险？
我能不能看到足够多的细节来信任系统？
```

但是 Audit Page 不能直接暴露 raw payload。原始 payload 可能包含：

- API key、token、cookie、Authorization header、环境变量。
- 本地绝对路径、用户目录、workspace 内敏感文件名。
- LLM prompt、completion、provider request/response。
- 文件内容、日志堆栈、命令输出。
- SQLite row、EventStream payload 或系统内部结构。
- 过长、过噪、普通用户无法理解的底层数据。

因此需要一套明确的 sanitized payload disclosure 机制：既让用户看到足够
可信的证据，又不把 Audit Page 变成无边界的日志/调试控制台。

---

## 2. Goals

1. 明确 Audit Page 可以展示什么 payload，不能展示什么 payload。
2. 明确后端如何把 source payload 转成 sanitized payload。
3. 明确 record detail 与 evidence detail 如何通过现有 contract 承载 disclosure。
4. 保持 A1-A14 mock scenarios 作为 parity fixtures。
5. 保持现有 Audit Page API 形状基本稳定，优先使用已有字段：
   `AuditDisclosure`、`SanitizedRawPayload`、`includeSanitizedPayload`。
6. 让缺失、隐藏、部分可见、脱敏、截断都成为显式状态，而不是静默失败。
7. 第一版覆盖 EventStream、log archive、config manifest；为 MessageStream、
   TaskInteractionTimeline、LLM/provider payload 留扩展点。

---

## 3. Non-goals

第一版不做：

- 直接展示 raw payload。
- 展示完整 LLM prompt / completion。
- 展示完整日志文件。
- 展示完整文件内容或完整 diff viewer。
- 做权限系统或多用户审计访问控制。
- 做通用日志搜索/trace debugger。
- 让前端执行脱敏规则。
- 用 Audit Page 修改任务、确认、配置或执行状态。

---

## 4. Terms

| Term | Meaning |
|---|---|
| Source payload | 后端事实源中的原始数据，例如 EventStream JSON、log line、config manifest。 |
| Productized record | 用户可理解的 `AuditRecord`，不是数据库 row 或 raw event。 |
| Evidence reference | `EvidenceRef` / `EvidenceSummary`，说明证据存在、来源、摘要和是否可见。 |
| Sanitized payload | 经后端白名单、脱敏、截断、结构化后的可展示内容。 |
| Disclosure | `AuditDisclosure`，说明 payload 是否存在、是否展示、为什么隐藏/脱敏/部分可见。 |
| Redaction | 对敏感字段或片段的替换，例如 `[redacted:secret]`。 |
| Hidden | 证据存在但不允许展示。 |
| Partial | 证据只展示部分内容，例如日志截断、字段省略、旧数据不完整。 |

---

## 5. Design Principles

1. **Backend owns sanitization.** 前端不能负责识别 secret、路径、prompt 或敏感
   字段。
2. **Default summary-only.** Snapshot 和 record list 永远不携带 sanitized payload。
3. **Explicit opt-in.** 只有 `includeSanitizedPayload=true` 的 record detail 或
   evidence detail 请求才可能返回 sanitized payload。
4. **No raw fallback.** Sanitizer 失败时返回 hidden/partial disclosure，不回退到 raw。
5. **Lossy but traceable.** Sanitized payload 可以有损，但必须说明 redaction、
   truncation 和 source。
6. **Source-specific rules.** EventStream、log、config、message、LLM payload 使用
   不同规则，不做一个粗暴 JSON dump。
7. **Small payload budget.** 第一版单个 sanitized payload 应控制在小尺寸内，避免
   Audit Page 变成日志页。
8. **User-readable first.** 展示内容优先解释“与这条审计记录相关的证据”，而不是
   展示所有字段。
9. **A1-A14 parity remains stable.** 现有 mock scenarios 不应因后端新增 disclosure
   细节而语义漂移。

---

## 6. Current Contract Baseline

当前 contract 已经有最小承载结构：

```ts
type AuditDisclosure = {
  rawPayloadAvailable: boolean;
  rawPayloadShown: boolean;
  redactionReason?: string | null;
  hiddenReason?: string | null;
  partialReason?: string | null;
  permissionReason?: string | null;
};

type SanitizedRawPayload = {
  format: "json" | "text";
  content: string;
  redactions: string[];
};

type EvidenceDetail = EvidenceSummary & {
  body: string;
  sanitizedPayload: SanitizedRawPayload | null;
  disclosure: AuditDisclosure;
};

type AuditRecordDetail = AuditRecord & {
  body: string;
  whyItMatters: string;
  evidence: EvidenceSummary[];
  disclosure: AuditDisclosure;
  rawPayload: SanitizedRawPayload | null;
};
```

第一版可以不破坏这些字段，只需要让后端真实填充它们。后续如果 UI 需要更细的
展示能力，再做 additive extension。

---

## 7. Disclosure Levels

第一版使用四个逻辑层级，映射到现有字段：

| Level | Meaning | Contract mapping |
|---|---|---|
| `none` | 没有可披露 payload，只有摘要。 | `rawPayloadAvailable=false`, `rawPayloadShown=false` |
| `hidden` | payload 存在，但策略或权限禁止展示。 | `rawPayloadAvailable=true`, `rawPayloadShown=false`, `hiddenReason` or `permissionReason` |
| `partial` | payload 可展示一部分，但不完整。 | `rawPayloadAvailable=true`, `rawPayloadShown=true`, `partialReason`, `sanitizedPayload` |
| `sanitized` | payload 经脱敏后可展示。 | `rawPayloadAvailable=true`, `rawPayloadShown=true`, `redactionReason?`, `sanitizedPayload` |

注意：`rawPayloadShown=true` 在现有 contract 中表示“sanitized payload 被展示”，
不是 raw payload 被展示。为了避免命名误导，文档和 UI 文案必须使用
“sanitized payload / sanitized evidence”，不要写“raw payload visible”。

---

## 8. Source Coverage

### 8.1 First-pass supported sources

| Source | First disclosure behavior | Notes |
|---|---|---|
| EventStream Action | 展示 action kind、action id、safe fields、task id、timestamp。 | 禁止完整 `model_dump()` 直出。 |
| EventStream Observation | 展示 observation kind、success/failure、safe summary、error code。 | 长输出截断；文件内容默认不展示。 |
| EventStream AuditObservation | 展示 verdict、concerns、summary。 | 不展示完整 audit prompt。 |
| Session log archive | 展示相关日志文件名、类别、少量 excerpt。 | 不展示完整日志文件。 |
| Logging config manifest | 展示 manifest hash、profile、archive path 的安全形式。 | 配置值按 allowlist。 |

### 8.2 Deferred sources

| Source | Reason to defer |
|---|---|
| MessageStream payload | 用户消息通常已在 UI 可见，但 response/context 仍需隐私策略。 |
| TaskInteractionTimeline | 适合作为更丰富排序和 evidence source，但不是 disclosure 第一依赖。 |
| LLM provider request/response | 高敏感；需要单独 provider payload policy。 |
| Tool stdout/stderr full body | 可能包含秘密、路径和大量噪声；第一版只摘要和截断。 |
| File content/diff | 需要 diff viewer 与文件敏感性规则；第一版只给文件路径和变更摘要。 |

---

## 9. Redaction Policy

### 9.1 Field denylist

任何 key/path 命中以下模式时默认 redacted：

```text
api_key
apikey
access_token
refresh_token
token
authorization
cookie
set_cookie
password
passwd
secret
private_key
ssh_key
credential
OPENAI_API_KEY
ANTHROPIC_API_KEY
DEEPSEEK_API_KEY
```

Replacement:

```text
[redacted:secret]
```

### 9.2 Path handling

路径默认 workspace-relative。以下内容默认 redacted 或 normalized：

| Input | Output |
|---|---|
| `/Users/name/project/session/file.py` | `workspace://session/file.py` |
| user home path outside workspace | `[redacted:path]` |
| temp path with random token | `[redacted:temp-path]` |
| archive/log path | show filename + category, not full absolute path |

### 9.3 Long text handling

| Source | First-pass limit |
|---|---|
| Event JSON string field | 2 KB after sanitization |
| Observation stdout/stderr summary | 20 lines or 4 KB |
| Log excerpt | 20 lines around selected record or 4 KB |
| Config manifest | only allowlisted keys |
| Redaction list | max 20 visible entries, then `+N more` |

If truncated:

```text
partialReason = "Payload was truncated for safe audit display."
redactions includes "truncated:<reason>"
```

### 9.4 LLM/provider payload

第一版默认不披露 provider raw request/response。

Mapping:

```text
rawPayloadAvailable = true
rawPayloadShown = false
hiddenReason = "LLM/provider payload is hidden by the audit disclosure policy."
```

后续如需展示，只能展示：

- provider name/model。
- request timestamp。
- retry count。
- response status/error code。
- token usage summary。
- prompt/completion 的产品化摘要，而不是原文。

---

## 10. Backend Architecture

### 10.1 New service seam

建议新增一个独立 service，不把 sanitizer 逻辑继续塞进 `DefaultUiQueryGateway`：

```python
class AuditPayloadDisclosureService(Protocol):
    def build_record_payload(
        self,
        record: AuditRecord,
        *,
        session: Session,
        include_sanitized_payload: bool,
    ) -> PayloadDisclosureResult: ...

    def build_evidence_payload(
        self,
        evidence: EvidenceSummary,
        *,
        session: Session,
        include_sanitized_payload: bool,
    ) -> PayloadDisclosureResult: ...
```

```python
@dataclass(frozen=True)
class PayloadDisclosureResult:
    disclosure: AuditDisclosure
    payload: SanitizedRawPayload | None
```

Gateway 仍负责 audit query orchestration；disclosure service 负责 source
lookup + sanitization + policy。

### 10.2 Internal components

```text
DefaultUiQueryGateway
  -> AuditPayloadDisclosureService
      -> SourcePayloadExtractor
          -> EventStreamPayloadExtractor
          -> LogArchivePayloadExtractor
          -> ConfigManifestPayloadExtractor
      -> PayloadSanitizer
      -> DisclosurePolicy
```

| Component | Responsibility |
|---|---|
| `SourcePayloadExtractor` | 从 record/evidence id 找到 source payload。 |
| `PayloadSanitizer` | 执行字段过滤、路径 normalization、截断、redaction。 |
| `DisclosurePolicy` | 判断 source 是否允许 sanitized display。 |
| `PayloadDisclosureResult` | 把 disclosure + payload 返回给 ViewModel。 |

### 10.3 Why not frontend sanitization

不能让前端 sanitization，原因：

1. 前端拿到 raw 就已经泄露。
2. secret detection 规则必须可测试、可审计、可集中升级。
3. Audit Page 需要保持 contract stable，不能让 UI 组件理解后端内部 payload。
4. 后端可以按 source 类型做更准确的 allowlist。

---

## 11. API Behavior

### 11.1 Snapshot

Snapshot 不返回 sanitized payload：

```http
GET /api/v1/sessions/{sessionId}/audit
```

Behavior:

- `records[].evidenceRefs[]` 可以标记 `available/hidden/redacted`。
- `records[].flags` 可以标记 `partial/hidden/redacted`。
- `selectedRecord.disclosure` 可以说明存在 hidden/partial。
- `selectedRecord.rawPayload` 默认 `null`。

### 11.2 Record detail

```http
GET /api/v1/sessions/{sessionId}/audit/records/{recordId}
  ?includeEvidence=true
  &includeSanitizedPayload=true
```

Behavior:

- `includeSanitizedPayload=false`：只返回 disclosure，不返回 payload。
- `includeSanitizedPayload=true`：如果策略允许，返回 `rawPayload`。
- 如果策略不允许：`rawPayload=null`，`disclosure.hiddenReason` 必须非空。
- 如果 source 不存在：`disclosure.partialReason` 或 `hiddenReason` 必须说明。

### 11.3 Evidence detail

```http
GET /api/v1/sessions/{sessionId}/audit/evidence/{evidenceId}
  ?includeSanitizedPayload=true
```

Behavior:

- Evidence detail 是最主要的 sanitized payload 展示入口。
- `EvidenceDetail.body` 永远是用户可读摘要。
- `EvidenceDetail.sanitizedPayload` 只在显式请求且策略允许时返回。
- 失败时返回 structured query error，不影响 snapshot/list。

---

## 12. UI Behavior

### 12.1 Record detail panel

Record detail 默认显示：

1. What happened
2. Why it matters
3. Outcome
4. Evidence references
5. Disclosure notes

如果 record 有可展示 sanitized payload：

- 第一版可以显示一个折叠区：`Sanitized evidence`
- 默认折叠。
- 展开时触发 evidence/detail query，而不是 snapshot 预载。
- 展示 redaction 和 truncation note。

### 12.2 Hidden evidence

如果 evidence hidden：

```text
Evidence is hidden by the audit disclosure policy.
```

如果用户可以查看 hidden reason：

```text
Reason: LLM/provider payload is hidden by policy.
```

如果不能查看：

```text
Reason is not available for this evidence.
```

### 12.3 Redacted payload

Redacted payload 必须同时展示：

- payload body。
- redaction count / reason list。
- partial/truncated note。

UI 不能只展示一段 JSON 而不说明它已经被处理过。

### 12.4 Copy behavior

第一版建议不提供 “copy sanitized payload” 按钮。等用户测试后再决定。

原因：

- 容易把脱敏内容误当完整证据传播。
- 容易和 Logs/Diagnostics 的开发者工作流混淆。

---

## 13. First Implementation Slice

### AP-012B: Design

Status: this document.

Output:

- sanitized payload disclosure technical design。
- contract / readiness links。

### AP-012C: Contract hardening

Backend:

- Add tests for `AuditDisclosure` and `SanitizedRawPayload` semantics.
- Confirm `includeSanitizedPayload=false` never returns payload.
- Confirm hidden/partial/redacted states are distinguishable.

Frontend:

- Keep A1-A14 mock scenarios stable.
- Add one or two focused mock evidence cases if needed:
  - sanitized EventStream payload
  - hidden LLM/provider payload

### AP-012D: Backend disclosure service

Implement:

- `AuditPayloadDisclosureService`.
- `PayloadSanitizer`.
- EventStream action/observation sanitizer.
- Log archive excerpt sanitizer.
- Config manifest sanitizer.

Do not:

- expose raw LLM payload.
- show full file content.
- make frontend reconstruct payloads.

### AP-012E: HTTP integration and UI rendering

Implement:

- `includeSanitizedPayload` query behavior.
- Evidence detail lazy fetch with sanitized payload.
- Detail panel disclosure rendering.
- Error/partial/hidden states.

### AP-012F: Readiness and parity

Validate:

- backend tests.
- frontend A1-A14 parity.
- hidden/partial/sanitized payload scenarios.
- docs/gaps/readiness updates.

---

## 14. Testing Matrix

| Layer | Tests |
|---|---|
| Model | `rawPayloadShown=true` requires payload; payload requires shown disclosure. |
| Sanitizer | secret key redaction, path normalization, long text truncation. |
| EventStream | action safe fields shown; observation output truncated/redacted. |
| Log archive | excerpt returned, full file not returned, secrets redacted. |
| Config | allowlisted config visible; secret-like keys hidden. |
| Gateway | no payload by default; payload only when requested and allowed. |
| HTTP | query param controls payload; hidden/partial states serialized correctly. |
| Frontend | disclosure notes, hidden reason, sanitized block, evidence load error. |
| Parity | A1-A14 scenarios unchanged unless explicitly extended. |

Minimum commands for implementation slice:

```text
uv run pytest tests/test_audit_page_contract_models.py tests/test_ui_query_gateway.py tests/test_ui_http_transport.py
uv run ruff check <changed backend files>
uv run mypy <changed backend files>
npm run test -- AuditPageRoute mockAuditScenarios platoApi platoRuntime
git diff --check
```

---

## 15. Open Questions

1. 是否需要在 UI 中把 `rawPayloadShown` 文案改成 “sanitized payload shown”？
   Contract 字段可以保持兼容，但文案应避免误导。
2. 第一版是否允许展示 command stdout/stderr 摘要？建议只展示截断摘要。
3. File content/diff 是否进入 Audit Page disclosure？建议推迟到专门的 file
   evidence design。
4. 是否需要区分“因为策略隐藏”和“因为权限隐藏”？现有字段可以区分，但第一版
   本地单用户场景可以先使用 policy hidden。
5. 是否需要为 redactions 建立结构化对象，而不是 `string[]`？第一版可先用
   `string[]`，后续如 UI 需要 redaction table 再扩展。

---

## 16. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Proceed with AP-012C: harden the Audit Page sanitized payload disclosure
contract tests while preserving the current frontend contract and A1-A14 mock
fixtures. Do not expose raw payloads. Add focused tests for hidden, partial,
redacted, and explicitly requested sanitized payload behavior.
```
