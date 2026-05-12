# 产品方向与架构洞察

## 产品目标

做一个有完整 UI 交互的 Agent 产品，用户无明显摩擦地使用核心功能。

时间线：1-2 个月完成可用 demo。

用途：
- 作为产品经理/工程师岗位的作品集
- 长期可演化为订阅制 SaaS

---

## 展示策略

**对外展示**：产品能做什么、用户怎么交互、解决哪些场景问题。

**保护内容**：核心架构设计、约束驱动编排、消息流模型等设计决策。

具体做法：
- 简历放 live demo 链接，不放仓库链接
- 面试初期只给 demo，进入深度环节再开放只读权限
- 云端部署是天然的源码保护——用户访问网页，拿不到服务端代码

---

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vite + React |
| 后端 | FastAPI + TaskWeavn 核心 |
| 桌面端 | Tauri（包 Web UI） |
| 数据库 | SQLite（已有） |
| LLM | litellm 多 provider，含 DeepSeek thinking |

打包分发：Tauri 生成 .dmg / .exe，Python 后端以 sidecar 方式随 app 启动，用户无感知。

---

## 平台架构：Session 即服务

### 核心洞察

TaskWeavn 从设计上把**交互**和**执行**分离：

- `MessageStream` 和 `TaskBus` 是独立的通信层
- Agent 在哪里执行对用户透明
- 任何能接入通信层的客户端都能驱动 session 工作

### Session API

用户可选择暴露 session 的对外接口，加 token 验证：

```
任意客户端（手机 / 脚本 / 第三方工具）
    │  POST /session/{id}/command  + token
    │  GET  /session/{id}/stream   (SSE 或 WebSocket)
    ▼
Session API 层
    ├── 写入 MessageStream
    └── 订阅 TaskBus → 推送给客户端
```

不暴露 = 纯本地运行；暴露 + token = 私有 API。用户控制边界。

### 移动端 + 桌面端协作场景

```
手机（发指令）──► 中继 / ngrok ──► 桌面端 Session
                                    ├── Workspace（本地文件）
                                    ├── ReAct Loop
                                    └── 交互输出回传
```

**用户场景**：桌面端发起长任务，离开后用手机发送指令或查看进度，回来继续深度操作。

产出和交互在桌面端，移动端只是轻量指令入口。这与"消息流替代阻塞中断"的设计天然契合——用户不在场也不会卡住 Agent。

### 参考设计

与 Jupyter Server、code-server 思路一致：本地计算资源，远程访问，客户端只是显示/指令层。区别在于 TaskWeavn 是 Agent 驱动，抽象层次更高。

---

## 通信层复用

不需要从零造轮子：

- **流式推送**：FastAPI + SSE / WebSocket
- **本地服务暴露**：ngrok / cloudflared，一行命令，无需维护中继基础设施
- **Token 验证**：FastAPI 原生支持

核心逻辑（AgentLoop、MessageStream、TaskBus）是壁垒，不替换。周边连接层大量复用现有工具。

---

## 当前优先级

1. **E3 完成**：session 持久化是跨设备协作的前提
2. **FastAPI 后端**：把 AgentLoop 包成 API，前端能真正跑起来
3. **Web UI 打通**：核心 Agent 流程端到端可用
4. **部署上线**：有公网可访问的 demo 链接

桌面端打包、移动端、软件集成——等核心跑通后再做。

---

## 集成原则

初期只打通 1-2 个最核心的集成，其余留接口不实现。每增加一个集成就增加一份维护成本。
