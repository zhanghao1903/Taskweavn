# Feature Plan: Web Retrieval Provider 抽象与 1.0 搜索工具接入

> Status: planned
> Type: 新特性支持
> Last Updated: 2026-05-13
> Owner/Session: planning session
> Target Implementation Session: tools / agent runtime execution session
> Related Code: `src/taskweavn/tools/`, `src/taskweavn/llm/`, `src/taskweavn/agent_loop.py`
> Related Research: `~/Downloads/llm_agent_web_search_tools.md`
> Related Plan: [LLM Provider 抽象、自动重试与 DeepSeek Thinking](llm-provider-retry-thinking.md)

---

## 1. 背景

TaskWeavn 当前的 Agent 只能在本地 workspace 内执行文件读写、Shell 与代码动作，缺少**对外部信息源的检索能力**。一旦任务涉及：

- 查最新文档 / changelog / API 变更
- 查 Stack Overflow / GitHub issue / 开源仓库
- 查事实型问题（版本号、价格、官方说明）
- 为后续 RAG / Collaborator Agent 提供 grounding 来源

agent 就只能依赖 LLM 训练语料里的旧知识，或让用户手工粘贴材料，这与"Task-first 通用 Agent 平台"的方向不一致。

业界目前提供搜索能力的方式分两类：

1. **Hosted tool** —— LLM provider 在服务端托管搜索工具（OpenAI `web_search`、Anthropic `web_search`）。应用只需声明工具，provider 负责搜索、抓取、引用。
2. **Client tool** —— LLM 只产出 tool call，应用自己执行第三方 Search API / 爬虫 / 浏览器。DeepSeek、绝大多数开源模型、OpenAI compatible 平台都走这条路。

TaskWeavn 已经在 [LLM Provider 计划](llm-provider-retry-thinking.md) 中确定了 multi-provider 抽象（OpenAI / Anthropic / DeepSeek / OpenRouter），因此搜索能力也必须是**跨 provider 的可插拔层**，而不是绑定在某一个模型上。

本计划的目标是在 1.0 阶段建立 `WebRetrievalProvider` 抽象层，落地最小可用的第三方 Search API provider（Tavily / Exa），并预留 OpenAI / Anthropic hosted search 接入位置，为后续 2.0 演进（缓存、抓取、SearXNG、Playwright）打好结构基础。

---

## 2. 目标

1. 建立 `WebRetrievalProvider` 抽象层，后续可以实现多种 provider：
   - `TavilySearchProvider`（默认，通用研究 / QA / RAG）
   - `ExaSearchProvider`（AI Coding / repo / changelog / docs）
   - `BraveSearchProvider`（更底层、可控的搜索数据源）
   - `OpenAIHostedSearchProvider`（hosted tool，OpenAI 主链路）
   - `ClaudeHostedSearchProvider`（hosted tool，Claude 主链路）
   - 预留 `SearXNGProvider` / `FirecrawlProvider` 等 2.0 自托管接入位
2. 统一 `SearchResult` 数据结构，让 Agent Core 不关心底层 provider 差异。
3. 提供 `web_search` 工具注册到 ToolRegistry，被 AgentLoop 通过 ReAct tool call 调用。
4. 区分 **hosted tool mode** 与 **client tool mode** 两种调用路径：
   - hosted：直接把工具声明透传给 LLM provider，结果通过 provider 回流。
   - client：TaskWeavn 自己执行搜索，并通过 `tool` message 把结果回灌给 LLM。
5. 第一批落地 client tool mode 的 Tavily / Exa provider，跑通 DeepSeek + web_search 跨模型主链路。
6. 在配置层暴露 mode / provider / top_k / enable_content_fetch / enable_cache，保持与 [LLM Provider 计划](llm-provider-retry-thinking.md) 配置入口风格一致。
7. 搜索调用要可观测：记录 provider、query、result count、latency、是否命中缓存、是否走 fallback。

---

## 3. 非目标

- 不在 1.0 中自建搜索引擎、爬虫、反爬绕过、PDF/OCR 深度处理、网页正文清洗模型。
- 不在 1.0 中实现 Playwright 浏览器自动化。
- 不在 1.0 中实现多轮 Deep Research Agent（query 改写 → 多轮搜索 → 综述）。
- 不在 1.0 中实现 Firecrawl / Crawl4AI 抓取链路；这是 2.0 阶段。
- 不在 1.0 中实现自托管 SearXNG；这是 2.0 阶段。
- 不在 1.0 中引入跨 provider fallback 策略；第一版只做单 provider 内的 retry。
- 不在本计划中重构 ToolRegistry / AgentLoop 的 tool 调用协议；只新增工具。
- 不在 1.0 中实现 hosted search 与 client search 之间的自动切换；由配置显式指定。

---

## 4. 当前代码事实

当前 `src/taskweavn/tools/` 下：

- 已有本地工具：FileRead / FileWrite / Bash / CodeAction 等。
- 工具按 OpenAI function-calling schema 注册，通过 LLM `tools=[...]` 参数下发。
- AgentLoop 在 LLM 返回 tool_call 时调用 `ToolRegistry.execute()`，并把结果作为 `role: tool` message 回传。
- **没有任何工具用于网络访问**；agent 知识被限制在本地 workspace + LLM 训练语料。

当前 `src/taskweavn/llm/` 下：

- 已有 provider 抽象（OpenAI / Anthropic / DeepSeek / OpenRouter / LiteLLM），见 [llm-provider-retry-thinking.md](llm-provider-retry-thinking.md)。
- 现有 `ChatRequest.tools` 只承载 client tool schema，没有 hosted tool 类型字段（例如 `{"type": "web_search"}`）。

当前配置入口：

- LLM 相关配置通过环境变量（`LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` 等）。
- 还没有统一的 `config.yaml`；[Configurable Logging Plan](configurable-logging-system.md) 将引入分层配置文件，本计划应与之对齐。

---

## 5. 主要问题

| 问题 | 影响 |
|---|---|
| Agent 无法访问外部信息 | 任何"查最新文档 / 查版本号 / 查事实"类任务都失败或胡编 |
| 不同 provider 搜索能力差异大 | 直接绑定某一家会让跨模型切换重做工具层 |
| Hosted tool 与 client tool 调用形态差异 | hosted 走 `tools=[{"type":"web_search"}]`，client 走 function call + tool result，必须有统一封装 |
| 搜索结果格式不统一 | Tavily / Exa / Brave / OpenAI hosted 返回字段不一样，AgentLoop 不应直接处理原始响应 |
| 搜索成本可能失控 | 每次搜索都是 $0.005–$0.015，叠加 LLM token 成本；没有缓存与配额会很快烧钱 |
| 搜索内容污染上下文 | 多条结果 + 正文一起塞进上下文会迅速吃满 token 预算 |
| 缺少引用记录 | 没有 url / source 持久化，无法在 final answer 中给出 citation，也无法审计 |
| 配置入口缺失 | 没有 `WEB_SEARCH_PROVIDER` 等入口，无法在不改代码的情况下切换 provider |

---

## 6. 设计原则

- **Provider owns transport**：第三方 SDK、base_url、auth、rate limit、retry 都在 provider 内部。
- **AgentLoop sees a tool, not a provider**：AgentLoop 只看到一个 `web_search` 工具；具体走哪个 provider、是 hosted 还是 client，由配置和 LLM provider 决定。
- **Unified result shape**：所有 provider 返回 `list[SearchResult]`，向上消除差异。
- **Hosted-aware but not hosted-only**：hosted tool 是优化路径，但默认主路径必须是 client tool，保证跨模型可用。
- **Client tool is cross-model**：DeepSeek / OpenAI / Claude / OpenRouter 都能通过同一套 client tool 协议调用 `web_search`。
- **Cost-aware by default**：1.0 必须有简单的内存级缓存与 top_k 限制；缓存策略可配置但默认开启。
- **Citation is first-class**：每个 SearchResult 必须有可追溯的 url / source；agent 最终回答必须能挂上引用。
- **No silent fallback**：如果配置了 `only=tavily`，请求失败时直接报错，不要悄悄回落到其他 provider。
- **Backwards compatible**：未配置 web search 时，TaskWeavn 行为与当前完全一致，工具不出现在工具列表里。

---

## 7. 核心抽象

### 7.1 SearchResult

```python
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    content: str | None = None
    published_at: str | None = None
    source: str | None = None         # provider 名 / 来源域名
    score: float | None = None        # provider 相关性分数
    raw: dict[str, Any] | None = None # 原始 payload，便于审计与 2.0 演进
```

字段约定：

- `snippet` 来自 provider 的简短摘要，长度通常 < 500 char。
- `content` 是 provider 抓回来的正文，可能为空；1.0 只在 `enable_content_fetch=True` 且 provider 原生支持时填充。
- `raw` 仅用于日志和审计，不进 LLM 上下文。

### 7.2 WebRetrievalProvider Protocol

```python
class WebRetrievalProvider(Protocol):
    name: str
    mode: Literal["hosted", "client"]

    async def search(self, request: SearchRequest) -> SearchResponse:
        ...

    def supports_hosted_invocation(self, llm_provider: str) -> bool:
        ...

    def hosted_tool_schema(self) -> dict[str, Any] | None:
        ...

    def client_tool_schema(self) -> dict[str, Any]:
        ...
```

说明：

- `mode` 是默认调用形态。hosted provider 也可能在不兼容模型上降级为 client（例如 OpenAIHostedSearchProvider 在 DeepSeek 下不可用）。
- `hosted_tool_schema()` 返回的是直接传给 LLM provider 的工具声明，例如 `{"type": "web_search"}`；不支持时返回 `None`。
- `client_tool_schema()` 返回的是 OpenAI function-calling 风格的 schema，所有 provider 必须实现，保证 client 模式始终可用。

### 7.3 SearchRequest

```python
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    recency: Literal["day", "week", "month", "year", "any"] | None = None
    include_domains: list[str] = []
    exclude_domains: list[str] = []
    enable_content_fetch: bool = False
    locale: str | None = None
    metadata: dict[str, Any] = {}
```

注意：

- `recency` / `include_domains` / `exclude_domains` 是跨 provider 的能力声明，不直接等同某个 API 参数；不支持时 provider 应忽略并在日志中提示。
- `enable_content_fetch=True` 时，provider 应尽量返回正文；否则只返回 snippet，节省 token 与成本。
- `top_k` 必须有上限（建议默认 5，最大 10），避免 LLM 滥用。

### 7.4 SearchResponse

```python
class SearchResponse(BaseModel):
    results: list[SearchResult]
    provider_name: str
    query: str
    cached: bool = False
    latency_ms: int | None = None
    cost_estimate: float | None = None
    raw: dict[str, Any] | None = None
```

关键点：

- `cached=True` 时不计入实际 provider 调用次数，便于成本可观测性。
- `cost_estimate` 单位为 USD，1.0 可以按 provider 公开报价做一次简单估算，不需要精确账单。

### 7.5 WebSearchCache

1.0 内存级缓存：

```python
class WebSearchCache(Protocol):
    def get(self, key: str) -> SearchResponse | None: ...
    def put(self, key: str, value: SearchResponse, ttl_seconds: int) -> None: ...
```

- 默认实现：进程内 LRU + TTL，TTL 默认 1 小时。
- key = hash(provider_name, query, top_k, recency, include_domains, exclude_domains)。
- 后续 2.0 可替换为 SQLite / Redis 实现。

---

## 8. Provider 基类需求

建议提供一个可复用基类：

```python
class BaseWebRetrievalProvider:
    name: str
    mode: Literal["hosted", "client"]
    cache: WebSearchCache | None
    retry_policy: RetryPolicy

    async def search(self, request: SearchRequest) -> SearchResponse:
        cached = self._cache_lookup(request)
        if cached is not None:
            return cached
        response = await self._with_retry(lambda: self._search_once(request))
        self._cache_store(request, response)
        return response

    async def _search_once(self, request: SearchRequest) -> SearchResponse:
        raise NotImplementedError

    def classify_error(self, exc: Exception) -> ErrorClassification:
        ...
```

### 8.1 错误分类

复用 LLM provider 的 `ErrorClassification`：

| 分类 | 示例 | 默认行为 |
|---|---|---|
| `retryable` | timeout / connection reset / 429 / 5xx | 指数退避重试 |
| `fatal_auth` | invalid api key / quota exhausted | 立即失败 |
| `fatal_request` | invalid query / 不支持的参数 | 立即失败 |
| `fatal_capability` | provider 不支持的搜索类型（例如 domain filter） | 立即失败或忽略参数并继续 |
| `unknown` | 无法识别异常 | 默认不重试 |

### 8.2 调用记录

每次调用记录到日志（与 LLM provider 日志同一体系）：

- provider_name
- query
- top_k / recency / domains
- result_count
- cached
- latency_ms
- cost_estimate
- retry_count
- error type / error message 摘要（如失败）

---

## 9. 第一批 Provider 设计

### 9.1 TavilySearchProvider（默认 client tool）

- 调用 Tavily Search API（`https://api.tavily.com/search`）。
- 必传参数：`query`、`max_results=top_k`。
- 可选参数：`search_depth`（"basic" / "advanced"），1.0 默认 basic；`include_raw_content=enable_content_fetch`。
- 响应映射：
  - `result.title` → `SearchResult.title`
  - `result.url` → `SearchResult.url`
  - `result.content` → `SearchResult.snippet`
  - `result.raw_content` → `SearchResult.content`
  - `result.score` → `SearchResult.score`
- 适合：通用研究、QA、RAG MVP。
- 成本估算：basic 1 credit，advanced 2 credit；可按 0.008 USD/credit 估算。

### 9.2 ExaSearchProvider（AI Coding / docs / repo）

- 调用 Exa Search API（`https://api.exa.ai/search`）。
- 可选 `useAutoprompt=true`（让 Exa 改写 query），1.0 默认关闭，保证 query 由 TaskWeavn agent 控制。
- 支持 `includeDomains` / `excludeDomains` / `startPublishedDate`。
- 如需正文，需额外调用 Exa `/contents`；当 `enable_content_fetch=True` 时 provider 内自动串接。
- 适合：repo / changelog / Stack Overflow / 技术文档检索。
- 成本估算：Search $7/1k + Contents $1/1k pages。

### 9.3 BraveSearchProvider（底层数据源）

- 调用 Brave Search API。
- 1.0 只做基础 Search，不接 Brave Answers。
- 主要作为 Tavily / Exa 不可用时的备选；不进入默认 fallback 链。
- 成本估算：$5/1k。

### 9.4 OpenAIHostedSearchProvider（hosted tool）

- mode = `hosted`，`hosted_tool_schema()` 返回 `{"type": "web_search"}`。
- 仅当 LLM provider == openai 时生效，否则 `supports_hosted_invocation()` 返回 False，AgentLoop 必须降级到 client provider。
- 不实现 `_search_once()`：搜索由 OpenAI 服务端完成，结果通过 LLM provider 直接回流。
- 主要工作是：透传工具声明、解析 response 中的 search citation，并在日志里记录"hosted search 已生效"。

### 9.5 ClaudeHostedSearchProvider（hosted tool）

- 与 OpenAI 类似，`hosted_tool_schema()` 返回 Claude 文档要求的 `web_search_*` 声明。
- 仅当 LLM provider == anthropic 时生效。
- 1.0 不做 dynamic filtering 的高级配置，使用默认行为。

### 9.6 Hosted 与 Client 的协作

AgentLoop 在准备一次 LLM 请求时：

```text
1. 读取配置：web_search.mode 与 provider
2. 如果 mode=hosted，且 provider.supports_hosted_invocation(llm_provider):
     把 provider.hosted_tool_schema() 加入 ChatRequest.tools
     不注册 client web_search 工具
3. 否则：
     把 provider.client_tool_schema() 注册到 ToolRegistry
     ChatRequest.tools 中带上 client schema
     LLM 返回 tool_call 时，AgentLoop 调用 provider.search()
```

任意时刻 AgentLoop 只暴露一个 `web_search` 工具；hosted vs client 的差异在 provider 层处理。

---

## 10. AgentLoop 集成

### 10.1 工具注册

- 新增 `WebSearchTool`，注册名 `web_search`。
- 工具描述固定为 "Search the public web for up-to-date information. Use when the answer requires recent or external facts."
- 参数 schema：`query: string`（必填）、`top_k: integer`（可选，默认 5，最大 10）、`recency: string`（可选枚举）、`include_domains: string[]`（可选）。

### 10.2 风险与 autonomy

- `WebSearchTool` baseline risk = `low`：不写本地文件，无副作用。
- 但 [CompositeAssessor](../../architecture/) 应能识别"涉及敏感 query"或"高成本调用"并升级风险。1.0 暂不实现 LLM 二次评估，只对 `top_k > 10` 或同一 query 短时间重复触发提示给上层。
- AutonomyGate 在 `careful` / `risk_gated` 模式下，第一次 web_search 仍应发出 ASK，让用户感知"agent 要联网"。

### 10.3 上下文压缩

- 默认把 `top_k` 个 `SearchResult` 序列化成 Markdown 列表，包含 title / url / snippet。
- `content` 字段只有当 `enable_content_fetch=True` 时拼入，且单条 content 截断在 2000 char 以内（1.0 简单策略，2.0 再做分块 / 摘要）。
- AgentLoop 把序列化结果作为 `role: tool` message 回传 LLM。

### 10.4 引用回写

- AgentLoop 在 final answer 阶段，如果 EventStream 中存在 `WebSearchObservation`，应把对应 url 列表附在最终回答里（具体由后续 Result Packaging plan 决定 UI 呈现，本计划只保证数据可用）。

---

## 11. 配置入口

第一版环境变量（与 [LLM Provider 计划](llm-provider-retry-thinking.md) 风格对齐）：

| 环境变量 | 说明 |
|---|---|
| `WEB_SEARCH_ENABLED` | `true` / `false`，默认 false |
| `WEB_SEARCH_MODE` | `hosted` / `client`，默认 client |
| `WEB_SEARCH_PROVIDER` | `tavily` / `exa` / `brave` / `openai` / `anthropic`，默认 tavily |
| `WEB_SEARCH_TOP_K` | 默认 5，上限 10 |
| `WEB_SEARCH_ENABLE_CONTENT_FETCH` | 默认 false |
| `WEB_SEARCH_CACHE_ENABLED` | 默认 true |
| `WEB_SEARCH_CACHE_TTL_SECONDS` | 默认 3600 |
| `TAVILY_API_KEY` | Tavily provider 优先读取 |
| `EXA_API_KEY` | Exa provider 优先读取 |
| `BRAVE_SEARCH_API_KEY` | Brave provider 优先读取 |

未来 [Configurable Logging](configurable-logging-system.md) 引入统一 `config.yaml` 后，应迁移到：

```yaml
web_search:
  enabled: true
  mode: client            # hosted | client
  provider: tavily        # tavily | exa | brave | openai | anthropic
  top_k: 5
  enable_content_fetch: false
  cache:
    enabled: true
    ttl_seconds: 3600
  providers:
    tavily:
      search_depth: basic
    exa:
      use_autoprompt: false
```

环境变量保持作为 v1 后备入口，避免阻塞 1.0 接入。

---

## 12. 执行切片

### Slice 1: Contracts

产出：

- `SearchResult` / `SearchRequest` / `SearchResponse`
- `WebRetrievalProvider` Protocol
- `BaseWebRetrievalProvider` 骨架
- `WebSearchCache` Protocol + 内存实现
- `WebSearchConfig`（mode / provider / top_k / 缓存）
- 错误层级（复用 LLM provider 的 `ErrorClassification`）

验收：

- 离线单元测试覆盖 contract 序列化、cache key 计算、retry policy 默认值。
- 不依赖任何真实网络。

### Slice 2: TavilySearchProvider

产出：

- `TavilySearchProvider._search_once`
- 响应映射到 `SearchResult`
- 重试 + 错误分类
- 缓存集成

验收：

- mock Tavily 响应：返回正确 `list[SearchResult]`。
- 429 后成功：自动重试。
- 401 / 403：不重试。
- 缓存命中：第二次 `search()` 不再调用 mock。

### Slice 3: WebSearchTool 与 AgentLoop 集成

产出：

- `WebSearchTool` 注册到 ToolRegistry
- AgentLoop 在 LLM tool_call 时调用 provider.search()
- Tool result 序列化为 Markdown
- EventStream 写入 `WebSearchAction` / `WebSearchObservation`

验收：

- 配置 `WEB_SEARCH_ENABLED=false` 时，工具不出现在工具列表。
- 配置 `WEB_SEARCH_ENABLED=true` + Tavily mock 时，LLM 能调用并拿到结果。
- 工具调用产生的 Action / Observation 能从 EventStream 回放。

### Slice 4: ExaSearchProvider

产出：

- `ExaSearchProvider._search_once`
- `enable_content_fetch=True` 时串接 `/contents`
- `include_domains` / `exclude_domains` / `recency` 映射

验收：

- mock Exa 响应：返回 `list[SearchResult]`。
- `enable_content_fetch=True`：响应中 `content` 非空。
- domain filter 透传正确。

### Slice 5: Hosted Search Provider 接入

产出：

- `OpenAIHostedSearchProvider`
- `ClaudeHostedSearchProvider`
- AgentLoop 根据 `mode=hosted` 把 provider.hosted_tool_schema() 注入 `ChatRequest.tools`
- LLM 响应中的 search citation 抽取到 EventStream

验收：

- LLM provider == openai：hosted schema 出现在请求里，client tool 不出现。
- LLM provider == deepseek + mode=hosted：自动降级到默认 client provider，并记录日志。
- 响应 citation 能写入 `WebSearchObservation`。

### Slice 6: BraveSearchProvider（可选）

产出：

- `BraveSearchProvider._search_once`
- 验收同 Tavily。

### Slice 7: Observability and Docs

产出：

- Web search 调用日志：provider / query / result_count / cached / latency / cost / retry。
- 用户文档：
  - 如何启用 web search
  - 如何切换 provider
  - 如何关闭 / 限制成本
  - hosted vs client 模式的区别和使用建议
- 在 `docs/architecture/` 下新增简短的 Web Retrieval Layer 说明（或并入 overview.md）。

验收：

- 失败日志能看出 provider / classification / retry。
- 成功日志能看出是否命中缓存、是否 hosted 模式。
- 文档示例能让新用户在 5 分钟内启用 Tavily 跑通一次搜索。

---

## 13. 测试计划

### 13.1 单元测试

- `test_web_search_contracts.py`
- `test_web_search_cache.py`
- `test_tavily_provider.py`
- `test_exa_provider.py`
- `test_brave_provider.py`
- `test_hosted_search_provider.py`
- `test_web_search_tool_integration.py`

### 13.2 关键测试场景

| 场景 | 期望 |
|---|---|
| WEB_SEARCH_ENABLED=false | 工具不暴露给 LLM，AgentLoop 行为与当前一致 |
| Tavily 429 后成功 | 自动重试，返回成功响应 |
| Tavily 连续 500 超过最大次数 | 抛结构化 retry exhausted error |
| Auth error | 不重试，错误信息清晰 |
| 相同 query 再次调用 | 命中缓存，cached=True，无第二次 HTTP 调用 |
| top_k=20 | 被夹到上限 10 |
| Exa enable_content_fetch=True | content 字段非空 |
| hosted mode + openai | 请求中包含 `{"type": "web_search"}` |
| hosted mode + deepseek | 自动降级到 tavily，并打降级日志 |
| Tool result 序列化 | Markdown 列表，包含 title / url / snippet，无 raw 字段 |
| EventStream 记录 | 一次搜索产生 1 个 Action + 1 个 Observation，可回放 |

### 13.3 手动验收

实现会话完成后，准备至少两个手动用例：

1. **DeepSeek + Tavily client tool**：
   - 用户问"OpenHands 最新 release 有哪些主要变化"。
   - LLM 触发 `web_search` tool call。
   - 后续 LLM 回答包含 url 引用。
   - 第二次相同 query 命中缓存。
2. **OpenAI hosted web_search**：
   - 配置 `WEB_SEARCH_MODE=hosted`、`WEB_SEARCH_PROVIDER=openai`、`LLM_PROVIDER=openai`。
   - 同一问题能跑通；EventStream 中能看到 hosted search 标记。

---

## 14. 风险与决策点

| 风险 | 处理 |
|---|---|
| 第三方 API 价格 / 接口变化 | provider 集中封装；实现前重新核对官方文档 |
| 搜索内容污染上下文 | 默认 snippet-only；`enable_content_fetch` 显式打开；单条 content 截断 |
| 成本失控 | 默认缓存开启 + top_k 上限；后续接入成本与配额系统 |
| hosted vs client 行为漂移 | 强制走统一 `SearchResult`；hosted citation 也要落到 EventStream |
| 安全 / 隐私（query 内容外泄） | 1.0 不发送 workspace 文件内容到 search API；只发送用户 query；日志可配置脱敏 |
| 用户拒绝联网 | autonomy 层第一次 web_search 必须经 ASK；用户拒绝后 agent 必须能优雅退化 |
| Provider rate limit | 复用 LLM retry policy；429/5xx 走指数退避 |
| 不同 provider 字段缺失（例如 published_at） | `SearchResult` 字段允许 None；不强行编造 |
| Hosted search 在不兼容模型下被误用 | `supports_hosted_invocation()` 显式判断，并降级 + 日志 |
| 与未来 RAG / 自托管检索的边界 | `WebRetrievalProvider` 只负责"公网检索"；内网 / workspace 检索由后续 RAG plan 处理，不在本计划内 |

---

## 15. 完成标准

该 feature 完成时，应满足：

- 有 `WebRetrievalProvider` 抽象，TaskWeavn 不再绑定单一搜索 API。
- 第一批 provider 至少完成 Tavily + Exa 两个 client 实现，以及 OpenAI hosted 接入。
- `web_search` 工具能被 DeepSeek / OpenAI / Claude / OpenRouter 任一 LLM provider 通过 client tool 模式调用。
- hosted mode 在兼容 LLM provider 下可用，不兼容时自动降级。
- 1.0 默认开启简单缓存 + top_k 上限，避免成本失控。
- 搜索调用全程可观测：provider / query / result_count / cached / latency / cost / retry。
- 用户可以通过环境变量启用 / 切换 / 关闭 web search，且默认关闭时 TaskWeavn 行为与当前完全一致。
- EventStream 记录 `WebSearchAction` / `WebSearchObservation`，可回放、可审计。
- 文档说明如何启用、切换 provider、控制成本，以及 hosted vs client 选择建议。

---

## 16. 状态

- Status: planned
- Created: 2026-05-13
- Owner/Session: planning session
- Target Implementation Session: tools / agent runtime execution session

预期前置依赖：

- [LLM Provider 抽象、自动重试与 DeepSeek Thinking](llm-provider-retry-thinking.md) —— 已完成，本计划复用其 retry policy 与错误分类。
- [Configurable Logging System](configurable-logging-system.md) —— 进行中；本计划落地的 web search 日志应直接接入新日志体系，避免重复设计。

预期后续 follow-ups：

- 2.0 阶段 1：引入 Firecrawl / Crawl4AI 做正文抓取，扩展 `enable_content_fetch=True` 的能力。
- 2.0 阶段 2：引入 SearXNG 自托管搜索入口，新增 `SearXNGProvider`。
- 2.0 阶段 3：动态网页场景接入 Playwright；与 Code Sandbox 共享浏览器运行时。
- 2.0 阶段 4：把 `WebRetrievalProvider` 与未来的 RAG / 内网检索层合并为统一的"Retrieval Layer"，分公网 / 内网 / workspace 三个域。
- 与未来"成本与配额"plan 对接：把 `cost_estimate` 接入预算 / 配额检查，触发 ASK 或硬拒绝。
- 与 Collaborator Agent 对接：让 Collaborator 在生成 Task Tree 时能主动调用 `web_search` 做事实核查。
