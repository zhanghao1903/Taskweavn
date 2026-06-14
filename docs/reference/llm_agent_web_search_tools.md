# LLM 应用中的网页搜索：Hosted Tools、Client Tools 与 1.0 选型

> 更新时间：2026-05-13  
> 目标读者：准备自建 Agent / AI Coding Agent / RAG Agent 的开发者  
> 核心问题：LLM 到底如何“搜索网页”？哪些能力由模型提供商托管，哪些需要应用自己实现？

---

## 0. 核心结论

LLM 本体并不会像人一样直接联网浏览网页。它最终仍然只接受 **token 输入**，并输出 token。

所谓“LLM 可以搜索网页”，本质上通常是：

```text
用户问题
  ↓
LLM 判断是否需要搜索
  ↓
LLM 发起 tool call
  ↓
搜索工具执行搜索 / 抓取 / 清洗 / 渲染
  ↓
工具把结果转成文本、JSON、Markdown、DOM 摘要或截图描述
  ↓
这些内容进入 LLM 上下文，变成 token
  ↓
LLM 基于这些 token 生成回答
```

因此，搜索能力分成两层：

1. **模型推理层**：LLM 决定搜什么、是否继续搜索、如何引用和回答。
2. **工具执行层**：搜索引擎、网页抓取器、浏览器、内容清洗器真正执行联网操作。

如果 LLM provider 提供 hosted web search，例如 OpenAI / Anthropic，那么 provider 会帮你托管工具执行层。  
如果 provider 只提供 function calling / tool calling，例如 DeepSeek 当前主要模式，那么你需要自己实现或接入第三方搜索工具。

---

## 1. LLM 应用如何搜索内容

### 1.1 LLM 仍然只接受 token 输入

无论是 GPT、Claude、DeepSeek，模型最终看到的不是“浏览器里的网页”，而是被序列化后的上下文，例如：

```json
{
  "title": "OpenHands Documentation",
  "url": "https://docs.all-hands.dev/...",
  "snippet": "OpenHands is an open-source agent platform...",
  "content": "OpenHands runs agent actions inside a sandboxed runtime..."
}
```

或者被清洗成 Markdown：

```markdown
# OpenHands Runtime

OpenHands runs agent actions inside a sandboxed runtime.
The runtime executes shell commands and file operations...
```

这些文本最终都会被 tokenizer 切成 token，再进入模型上下文。

### 1.2 Hosted tool 模式

Hosted tool 是指工具由 LLM provider 在服务端执行。应用只需要在请求里声明工具：

```json
{
  "model": "gpt-5.5",
  "tools": [
    { "type": "web_search" }
  ],
  "input": "今天 OpenHands 有什么最新更新？"
}
```

大致流程：

```text
用户问题
  ↓
你的应用调用 LLM API，并声明 web_search
  ↓
LLM 判断需要搜索
  ↓
Provider 服务端执行搜索
  ↓
Provider 把搜索结果放回模型上下文
  ↓
LLM 输出带引用的回答
```

优点：

- 接入简单。
- 搜索、引用、上下文压缩和模型推理结合更紧密。
- 对普通开发者来说，效果通常比自己临时拼搜索工具更稳定。

缺点：

- 成本由 provider 定义，通常有额外 tool call 费用。
- 不同 provider 的工具行为、返回格式和可控参数不同。
- 跨模型时不可复用，例如 OpenAI 的 hosted search 不能直接给 DeepSeek 用。
- 私有化、缓存、审计和特殊页面处理能力有限。

### 1.3 Client tool 模式

Client tool 是指模型只负责“提出工具调用请求”，真正执行由你的应用完成。

```text
用户问题
  ↓
LLM 输出 tool call：
  web_search({"query": "OpenHands latest release"})
  ↓
你的 Agent Runtime 调用搜索 API / 爬虫 / 浏览器
  ↓
你的应用把结果作为 tool result 传回 LLM
  ↓
LLM 基于结果继续推理并回答
```

示例工具定义：

```json
{
  "type": "function",
  "function": {
    "name": "web_search",
    "description": "Search the web and return relevant pages.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Search query"
        },
        "top_k": {
          "type": "integer",
          "description": "Number of results"
        }
      },
      "required": ["query"]
    }
  }
}
```

模型可能返回：

```json
{
  "name": "web_search",
  "arguments": {
    "query": "OpenHands latest release architecture",
    "top_k": 5
  }
}
```

你的代码再真正执行：

```python
results = search_provider.search(query="OpenHands latest release architecture", top_k=5)
```

然后把结果返回给模型：

```json
{
  "role": "tool",
  "name": "web_search",
  "content": [
    {
      "title": "OpenHands Release Notes",
      "url": "https://github.com/...",
      "snippet": "...",
      "content": "..."
    }
  ]
}
```

优点：

- 跨模型一致性好。
- DeepSeek、OpenAI、Claude 都可以共用同一套搜索层。
- 可以接入私有搜索、内网文档、公司知识库。
- 可以自定义缓存、审计、去重、排序、内容清洗和安全策略。

缺点：

- 需要自己实现工具执行层。
- 搜索质量、网页清洗质量、引用质量都要自己负责。
- 动态网页、登录页面、复杂表格、PDF、图表会带来额外工程复杂度。

---

## 2. 搜索工具的几种类型

### 2.1 LLM provider hosted web search

代表：

- OpenAI `web_search`
- Anthropic Claude `web_search`

特点：

```text
LLM provider 负责搜索执行
你的应用只负责声明工具
模型决定是否搜索和如何使用结果
```

适合：

- 快速构建高质量搜索问答。
- 不想处理网页抓取、正文清洗、引用生成。
- 当前主模型就是 OpenAI / Claude。

不适合：

- 多模型统一搜索层。
- DeepSeek 等不提供 hosted search 的模型。
- 私有化或内网搜索。
- 需要强可控网页抓取策略的场景。

---

### 2.2 第三方 Search API / Search for LLM API

代表：

- Tavily
- Exa
- Brave Search API
- Perplexity Search API / Sonar API

特点：

```text
第三方服务提供搜索结果、网页内容、摘要或答案
你的 Agent 负责调用 API，并把结果传给 LLM
```

适合：

- DeepSeek + web search。
- 跨模型 Agent。
- 1.0 版本快速跑通链路。
- 不想自己维护搜索引擎和爬虫。

这类服务通常分两种：

#### A. Search API

返回搜索结果、URL、snippet、网页正文片段。  
你的 Agent 自己负责总结和回答。

```text
query → search results → LLM 总结
```

#### B. Answer API / Research API

服务本身也会调用模型，直接返回带引用的答案。

```text
query → third-party API 直接返回 answer + citations
```

对于自建 Agent，我更建议 1.0 优先用 **Search API**，而不是直接用 Answer API。  
因为这样可以保留你的 Agent 编排能力：query 改写、工具选择、继续搜索、引用整合、最终回答都在你的系统里完成。

---

### 2.3 开源元搜索引擎

代表：

- SearXNG

特点：

```text
聚合多个搜索引擎结果
返回 URL / title / snippet
可以自托管
```

适合：

- 自建搜索入口。
- 降低第三方 API 依赖。
- 注重隐私和可控性。

局限：

- 它主要解决“找到 URL”的问题。
- 不负责高质量正文抽取。
- 不负责动态网页渲染。
- 不负责 LLM 上下文压缩和引用管理。

所以 SearXNG 更像搜索入口，而不是完整的 LLM web retrieval layer。

---

### 2.4 网页抓取与内容清洗工具

代表：

- Firecrawl
- Crawl4AI

特点：

```text
URL → clean Markdown / structured JSON / screenshot / extracted content
```

适合：

- 把网页转成 LLM 更容易处理的格式。
- 抓取正文。
- 处理部分动态页面。
- 为 RAG / Agent 提供网页内容输入。

它们通常和搜索工具组合使用：

```text
Search API / SearXNG 找 URL
  ↓
Firecrawl / Crawl4AI 抓取正文
  ↓
正文清洗、截断、分块
  ↓
LLM 回答
```

---

### 2.5 浏览器自动化工具

代表：

- Playwright

特点：

```text
真实打开浏览器
渲染网页
点击、输入、滚动、截图、提取 DOM
```

适合：

- JavaScript 动态页面。
- 登录页面。
- 网页操作任务。
- UI 测试。
- 复杂交互型网站。
- 需要截图或页面布局理解的任务。

不适合 1.0 作为默认方案，因为它比较重：

- 需要浏览器运行环境。
- 需要处理超时、反爬、登录态、Cookie、安全边界。
- 工具返回内容需要再清洗成 LLM 可读上下文。

---

## 3. 哪些 LLM provider 支持 hosted search，哪些需要 client tool

| Provider | Hosted web search | Client tool / function calling | 说明 |
|---|---:|---:|---|
| OpenAI | 支持 | 支持 | Responses API 可声明 `web_search`；也可以自定义 function tool |
| Anthropic / Claude | 支持 | 支持 | Claude API 支持 server-side `web_search`；也支持 client tools |
| DeepSeek | 当前主要依赖 client tool | 支持 | DeepSeek function calling 文档显示，函数功能需要用户提供，模型本身不执行具体函数 |
| Perplexity | 提供 web-grounded API / Search API | 可作为外部搜索服务 | 更像“带搜索的模型/API”或第三方搜索服务 |
| 其他 OpenAI-compatible 模型 | 不一定 | 通常支持部分 tool calling | 要看具体平台是否实现 hosted tool，而不是只看协议是否兼容 |

### 3.1 OpenAI

OpenAI Responses API 可以通过 `tools` 声明：

```json
{
  "tools": [
    { "type": "web_search" }
  ]
}
```

模型可以根据用户问题决定是否搜索，也可以由应用强制使用搜索。

适合：

```text
OpenAI 主模型
需要高质量引用
需要快速跑通 web search
```

### 3.2 Anthropic / Claude

Claude API 支持 server-side web search。  
当你把 web search 工具加入 API 请求后：

```text
Claude 判断何时搜索
Anthropic API 执行搜索
搜索结果进入 Claude 上下文
Claude 输出带引用的回答
```

新版 `web_search_20260209` 还支持 dynamic filtering。它可以在搜索结果进入上下文前做过滤，减少无关内容进入上下文。

适合：

```text
Claude 主模型
研究、写作、事实核查
技术文档搜索
```

### 3.3 DeepSeek

DeepSeek 当前更适合按 client tool 方式使用。

DeepSeek function calling 的官方流程是：

```text
用户提问
  ↓
模型返回 function call
  ↓
用户应用执行函数
  ↓
用户应用把函数结果传回模型
  ↓
模型生成最终回答
```

文档中特别说明：函数功能需要由用户提供，模型本身不执行具体函数。

所以，如果你用 DeepSeek 做 Agent，并希望它能搜索网页，通常要：

```text
DeepSeek 生成 web_search tool call
  ↓
你的 Agent Runtime 调用 Tavily / Exa / Brave / SearXNG
  ↓
把结果传回 DeepSeek
```

---

## 4. 外部搜索工具与开源实现

### 4.1 开源实现

| 工具 | 类型 | 用途 | 优点 | 局限 |
|---|---|---|---|---|
| SearXNG | 元搜索引擎 | 聚合搜索结果 | 可自托管、隐私友好、免费开源 | 主要返回搜索结果，不解决正文清洗 |
| Firecrawl | 搜索/抓取/清洗 API | 给 AI Agent 提供 clean web data | 开源 + hosted，能输出 Markdown/JSON 等 | hosted 需要付费，自托管有部署成本 |
| Crawl4AI | LLM-friendly crawler | 网页抓取、Markdown 输出、AI-ready crawling | 开源，面向 LLM/Agent/RAG | 仍需自己做搜索编排和上下文管理 |
| Playwright | 浏览器自动化 | 渲染、点击、输入、截图、动态页面 | 能处理真实浏览器场景 | 1.0 偏重，维护成本较高 |

### 4.2 推荐组合

#### 低成本自托管组合

```text
SearXNG
  ↓
Crawl4AI
  ↓
LLM
```

适合后续 2.0，不适合 1.0 一开始就做。

#### 更完整的网页读取组合

```text
Search API
  ↓
Firecrawl / Crawl4AI
  ↓
内容清洗、分块、去重
  ↓
LLM
```

#### 动态页面增强组合

```text
Search API
  ↓
Playwright 渲染
  ↓
DOM / screenshot / text extraction
  ↓
LLM
```

---

## 5. Hosted tool 与第三方 Search API 费用比较

> 注意：价格变化很快，以下为 2026-05-13 核对到的公开价格。实际使用前应再次查看官方 pricing 页面。

| 服务 | 类型 | 费用结构 | 适合场景 |
|---|---|---|---|
| OpenAI `web_search` | LLM provider hosted tool | Web search：$10 / 1k calls；搜索内容 token 按所选模型价格计费 | OpenAI 主链路，高质量搜索和引用 |
| Anthropic Claude `web_search` | LLM provider hosted tool | $10 / 1k searches；搜索生成内容按标准 token 计费 | Claude 主链路，研究、写作、技术搜索 |
| Tavily | 第三方 Search API | Free：1,000 credits/月；Pay-as-you-go：$0.008 / credit；basic search 通常 1 credit，advanced 2 credits | Agent/RAG MVP，通用网页搜索 |
| Exa | 第三方 Search API | Search：$7 / 1k requests；Contents：$1 / 1k pages；Answer：$5 / 1k requests；Deep Search：$12–15 / 1k requests | Coding Agent、文档搜索、repo/changelog/Stack Overflow |
| Brave Search API | 搜索基础设施 API | Search：$5 / 1k requests；Answers：$4 / 1k queries + token 费；每月含 $5 credits | 通用搜索、自己控制总结层 |
| Perplexity Search / Sonar | Search API / web-grounded answer API | Search API 提供 ranked web results；Sonar Pro 等按 request fee + token 费计价，fast/pro 随上下文大小变化 | 直接要 web-grounded answer，或使用 Perplexity 搜索栈 |

### 5.1 成本理解

Hosted web search 通常不是“只算 token”。  
以 OpenAI / Claude 为例，它们的 web search 都有额外的搜索调用费，同时搜索内容进入上下文后，还会产生 input token 成本。

可以理解成：

```text
总成本 =
  搜索工具调用费
  + 搜索结果内容 token 费
  + 用户 prompt token 费
  + 模型输出 token 费
```

第三方 Search API 的成本则通常是：

```text
总成本 =
  第三方搜索 API 请求费
  + LLM input token 费
  + LLM output token 费
```

如果第三方 API 已经直接生成 answer，例如 Answer API / Sonar API，则还可能包含：

```text
answer request fee
+ provider 自身 token 费
```

---

## 6. 1.0 版本路径选择

你的判断是合理的：**1.0 版本尽量使用外部工具，不管是模型 provider 的 hosted tool，还是第三方 Search API。先把 Agent 链路跑通，再考虑自建。**

### 6.1 不建议 1.0 自建完整搜索工具

1.0 阶段不建议一上来就做：

```text
搜索引擎
网页爬虫
动态网页渲染
正文清洗
PDF 解析
反爬处理
引用系统
缓存系统
```

这些都很容易把项目拖成“爬虫系统”，而不是 Agent 项目。

1.0 的核心目标应该是：

```text
证明 Agent 能够：
1. 判断是否需要搜索
2. 生成合理 query
3. 调用搜索工具
4. 整合多来源信息
5. 给出带引用的回答
6. 记录工具调用过程
7. 支持不同模型切换
```

### 6.2 推荐 1.0 架构

不要把搜索工具写死在某个 provider 上。  
应该做一个抽象层：

```text
Agent Core
  ↓
Tool Router
  ↓
WebRetrievalTool Interface
  ↓
Provider Implementations
    ├── OpenAIHostedSearchProvider
    ├── ClaudeHostedSearchProvider
    ├── TavilySearchProvider
    ├── ExaSearchProvider
    ├── BraveSearchProvider
    └── FutureSelfHostedSearchProvider
```

### 6.3 统一返回结构

不管底层用 OpenAI、Claude、Tavily、Exa 还是 Brave，建议统一成这个结构：

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    content: Optional[str] = None
    published_at: Optional[str] = None
    source: Optional[str] = None
```

搜索工具接口：

```python
from abc import ABC, abstractmethod

class WebRetrievalProvider(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        recency: str | None = None,
        domains: list[str] | None = None,
    ) -> list[SearchResult]:
        ...
```

这样后续替换工具不会影响 Agent Core。

### 6.4 推荐 1.0 provider 选择

#### 默认方案

```text
Tavily 或 Exa
```

如果你的 Agent 偏通用研究、问答、RAG：

```text
优先 Tavily
```

如果你的 Agent 偏 AI Coding、查文档、查 repo、查 changelog：

```text
优先 Exa
```

#### OpenAI / Claude 增强方案

```text
OpenAI 模型 → 可选 OpenAI hosted web_search
Claude 模型 → 可选 Claude hosted web_search
DeepSeek 模型 → 走 Tavily / Exa / Brave
```

也可以做成配置项：

```yaml
web_search:
  mode: third_party   # hosted | third_party | self_hosted
  provider: exa       # openai | anthropic | tavily | exa | brave | searxng
  top_k: 5
  enable_content_fetch: true
  enable_cache: true
```

### 6.5 1.0 最小闭环

1.0 可以只做这些：

```text
1. LLM 判断是否需要搜索
2. LLM 生成 search query
3. WebRetrievalTool 调用 Tavily / Exa
4. 返回 title / url / snippet / content
5. LLM 基于搜索结果回答
6. 输出引用来源
7. 记录 tool call 日志
8. 做简单缓存，避免重复搜索
```

### 6.6 暂时不要做的事情

1.0 暂时不建议做：

```text
Playwright 浏览器自动化
复杂动态网页处理
大规模爬虫
反爬绕过
PDF/OCR 深度处理
自建搜索索引
复杂网页去噪模型
多轮 research agent
```

这些可以放到 2.0。

### 6.7 2.0 演进方向

当 1.0 链路稳定后，可以逐步替换或增强：

```text
阶段 1：
  Tavily / Exa / Brave 跑通搜索链路

阶段 2：
  加入缓存、去重、引用管理、搜索日志

阶段 3：
  加入 Firecrawl / Crawl4AI 做网页正文抓取

阶段 4：
  加入 SearXNG 做自托管搜索入口

阶段 5：
  针对动态网页加入 Playwright

阶段 6：
  建立自己的 Web Retrieval Layer：
    search
    fetch
    extract
    rank
    summarize
    cite
    cache
```

---

## 7. 对个人 Agent 项目的最终建议

你的 1.0 路径可以定成：

```text
第一优先级：
  使用 Tavily / Exa 跑通跨模型搜索工具链路。

第二优先级：
  在 OpenAI / Claude 模式下，可选接入 provider hosted web_search。

第三优先级：
  加入 Brave Search API 作为更底层、可控的搜索数据源。

第四优先级：
  2.0 再引入 SearXNG + Crawl4AI / Firecrawl + Playwright。
```

项目展示时，不要强调“我自己写了一个搜索引擎”。  
更应该强调：

```text
我设计了一个可插拔的 Agent Web Retrieval Layer，
支持 LLM provider hosted tools、第三方 Search API、自托管搜索工具，
并统一了搜索结果结构、引用管理、缓存和工具调用日志。
```

这比“临时接一个搜索 API”更能体现架构设计能力。

---

## 8. 参考资料

- OpenAI Web Search Tool: https://developers.openai.com/api/docs/guides/tools-web-search
- OpenAI API Pricing: https://developers.openai.com/api/docs/pricing
- Anthropic Claude Web Search Tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- DeepSeek Function Calling: https://api-docs.deepseek.com/guides/function_calling
- Tavily Pricing: https://www.tavily.com/pricing
- Tavily API Credits: https://docs.tavily.com/documentation/api-credits
- Exa Pricing: https://exa.ai/pricing
- Brave Search API Pricing: https://api-dashboard.search.brave.com/documentation/pricing
- Perplexity Search API: https://docs.perplexity.ai/docs/search/quickstart
- Perplexity API Pricing: https://docs.perplexity.ai/docs/getting-started/pricing
- SearXNG: https://searxng.org/
- Firecrawl: https://github.com/firecrawl/firecrawl
- Crawl4AI: https://docs.crawl4ai.com/
- Playwright: https://playwright.dev/
