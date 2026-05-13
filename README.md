# Millipede

> **Humans-in-the-loop ML Agent 平台** — Phase 1: AutoDA L1 MVP

Millipede 是一个面向数据科学团队的 AI Agent 平台。用户上传数据集、描述分析目标，系统自动完成数据探查、清洗、分析，并交付结构化的 `analysis_pack`（数据报告 + 特征建议），供下游 AutoML 流程直接使用。

Phase 1 实现了 **AutoDA L1** 全自动通道：无需人工干预，Agent 自主完成从数据上传到交付的完整闭环。

---

## 架构概览

```
Customer UI          Engineer UI
    │                    │
    ▼                    ▼
FastAPI Backend ──── WebSocket (Redis Pub/Sub)
    │
    ├── Celery Worker
    │       └── AutoDA Agent Loop
    │               ├── LLM (DeepSeek / 豆包 / 千问 / OpenAI / Anthropic)
    │               └── Docker Sandbox (pandas, sklearn, matplotlib…)
    │
    ├── PostgreSQL (pgvector)
    ├── Redis (任务队列 + 事件总线)
    └── MinIO (文件存储)
```

### 核心抽象

| 概念 | 说明 |
|---|---|
| **Project** | 生命周期容器，持有目标、数据和版本 |
| **RunCard** | 执行实体，记录每次 Agent 运行的全部状态和产物 |
| **task_level** | L1=全自动，L2=双门控人工审核（Phase 2），L3=指定工程师（Phase 2） |
| **analysis_pack** | 交付物：manifest + data_report + feature_hints（供 AutoML 消费） |

### AutoDA L1 状态机

```
DRAFT → REQ_READY → PRE_ANALYZING → PREPROCESSING → DA_PLANNING
      → DATA_ANALYZING → AWAIT_REVIEW_DA_REPORT → AWAIT_DISPATCH_DA_REPORT
      → PACKAGING → DELIVERED
```

### Agent 执行循环

```
目标 → LLM 规划 → LLM 生成代码 → Docker 沙盒执行
     → LLM 评估 → [失败] LLM 修复代码（最多 3 次）→ 下一步
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 15 + React 19 + TanStack Query + Zustand + Tailwind |
| 后端 | FastAPI + SQLAlchemy (asyncpg) + Alembic + Pydantic v2 |
| 任务队列 | Celery + Redis |
| LLM 路由 | LiteLLM（DeepSeek / 豆包 / 千问 / OpenAI / Anthropic） |
| 状态机 | transitions |
| 沙盒 | Docker（session-based，一个 RunCard 一个容器） |
| 存储 | MinIO (S3-compatible) |
| 数据库 | PostgreSQL 16 + pgvector |
| 事件总线 | Redis Pub/Sub |

---

## 快速启动

### 前置条件

- Docker Desktop（已启动）
- `millipede-sandbox:latest` 镜像（见下方）

### 1. 构建沙盒镜像

```bash
docker build -t millipede-sandbox:latest infra/sandbox/
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

至少填写一个 LLM API Key，推荐 DeepSeek（性价比最高）：

```env
DEEPSEEK_API_KEY=sk-your-key-here
DEFAULT_LLM_MODEL=deepseek/deepseek-chat
```

其他支持的模型：

| 提供商 | 模型格式 | 环境变量 |
|---|---|---|
| DeepSeek | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` |
| 豆包（火山引擎） | `volcengine/<endpoint-id>` | `VOLCENGINE_API_KEY` + `DOUBAO_MODEL_ID` |
| 千问（阿里云） | `openai/qwen-plus` | `DASHSCOPE_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |

### 3. 启动服务

```bash
docker compose up -d
```

服务启动后：

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| MinIO 控制台 | http://localhost:9001 |

### 4. 初始化数据库

```bash
docker compose exec backend alembic upgrade head
```

---

## 使用流程

### Customer 端

1. 访问 http://localhost:3000，注册账号
2. 新建项目：选择 AutoDA，填写分析目标
3. 上传数据文件（CSV / XLSX / PDF，最大 500MB）
4. 点击「Submit」提交，RunCard 进入自动分析流程
5. 在项目详情页通过 WebSocket 实时查看进度

### Engineer 端（L2/L3，Phase 1 中为管理员预览）

1. 将账号 role 改为 `engineer`（数据库直接修改）
2. 访问 http://localhost:3000/engineer/reviews
3. 查看待审核 RunCard 的各阶段输出
4. Accept / Modify / Reject，然后 Confirm Dispatch

---

## API 速查

### 认证

```bash
# 注册
POST /api/v1/auth/register
{"email": "...", "password": "...", "display_name": "...", "org_name": "..."}

# 登录
POST /api/v1/auth/login
{"email": "...", "password": "..."}
```

### 项目 & RunCard

```bash
POST   /api/v1/projects                          # 创建项目
POST   /api/v1/projects/{id}/uploads             # 上传数据
POST   /api/v1/projects/{id}/runcards            # 提交运行
GET    /api/v1/projects/{id}/runcards            # 查看运行列表
```

### 工程师审核

```bash
GET    /api/v1/engineer/reviews                  # 待审核列表
GET    /api/v1/engineer/reviews/{id}/outputs     # 阶段产物
POST   /api/v1/engineer/reviews/{id}/action      # accept|modify|reject
POST   /api/v1/engineer/reviews/{id}/dispatch    # 确认派发
```

### WebSocket

```
ws://localhost:8000/ws/runcards/{runcard_id}
```

事件格式：`{"event_type": "runcard.state_changed", "payload": {"from": "...", "to": "..."}}`

---

## 项目结构

```
Millipede/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── customer/       # auth, projects, runcards, uploads
│   │   │   ├── engineer/       # reviews, dispatch
│   │   │   └── ws/             # WebSocket
│   │   ├── auth/               # JWT, bcrypt, role deps
│   │   ├── config.py
│   │   ├── domain/
│   │   │   └── pack/           # analysis_pack 构建器
│   │   ├── infra/
│   │   │   ├── db/             # SQLAlchemy models + migrations
│   │   │   ├── eventbus/       # Redis Pub/Sub
│   │   │   ├── llm/            # LiteLLM 多提供商路由
│   │   │   ├── sandbox/        # Docker 沙盒客户端
│   │   │   └── storage/        # MinIO 客户端
│   │   ├── orchestration/
│   │   │   ├── agent_runner/   # AgentRunner + prompts
│   │   │   └── state_machine/  # AutoDAStateMachine
│   │   └── workers/
│   │       └── tasks/          # autoda.py, packaging.py
│   ├── alembic/
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── customer/       # 项目列表、创建、详情
│       │   └── engineer/       # 审核列表、审核详情
│       ├── lib/                # axios client, WebSocket
│       └── store/              # Zustand auth store
├── infra/
│   └── sandbox/                # Dockerfile for millipede-sandbox
└── docker-compose.yml
```

---

## feature_hints Schema（v1.0）

`analysis_pack` 中的 `feature_hints` 字段，供 Phase 2 AutoML 直接消费：

```json
[
  {
    "field": "species",
    "hint_type": "target",
    "description": "目标列，分类任务标签",
    "suggested_transform": "label_encode"
  },
  {
    "field": "sepal_length",
    "hint_type": "high_cardinality",
    "description": "连续数值型特征，分布正常",
    "suggested_transform": null
  }
]
```

`hint_type` 取值：`target` · `high_cardinality` · `leakage_risk` · `low_variance` · `datetime` · `text`

`suggested_transform` 取值：`label_encode` · `one_hot` · `drop` · `log` · `bin` · `tfidf` · `null`

---

## Phase 路线图

| Phase | 状态 | 内容 |
|---|---|---|
| **Phase 1** | ✅ 完成 | AutoDA L1 全自动通道，Docker 沙盒，多 LLM 提供商，端到端交付 |
| Phase 2 | 🔜 | AutoDA L2/L3 双门控审核，E2B/Daytona 沙盒，Temporal 工作流，AutoML 接入 |
| Phase 3 | 📋 | 模型工厂集成，AIDE 增强，多租户，企业级权限 |

---

## 开发说明

```bash
# 本地后端开发（需要 docker compose up postgres redis minio）
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# 数据库迁移
alembic revision --autogenerate -m "描述"
alembic upgrade head

# 本地前端开发
cd frontend
npm install
npm run dev
```

---

## License

MIT
