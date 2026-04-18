<div align="center">

# docuAI

**上传文档，直接对话。**

基于 RAG 的文档问答应用，支持 PDF 语义检索、流式回答与来源引用卡片。

[![CI](https://github.com/rol1an/docuAI-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/rol1an/docuAI-RAG/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-336791)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 功能亮点

- **文档上传** — 支持 PDF，自动分块向量化入库
- **语义检索** — pgvector HNSW 索引 + CrossEncoder 二阶段精排
- **流式问答** — 逐 Token 输出，直接 RAG Pipeline（非 Agent，稳定可预期）
- **Citation 卡片** — 每条回答附带引用来源，显示文件名、页码、相关度
- **多轮对话** — 对话历史持久化，侧边栏随时切换
- **模型选择** — 前端下拉切换 LLM 模型

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | Next.js 15 · React 19 · Tailwind CSS · shadcn/ui · Zustand |
| 后端 | FastAPI · Pydantic v2 · SQLAlchemy 2.0 async |
| 数据库 | PostgreSQL 17 + pgvector 0.8.2 |
| 向量检索 | HNSW 索引 · text-embedding-3-small (1536 维) |
| 精排 | CrossEncoder (cross-encoder/ms-marco-MiniLM-L6-v2) |
| LLM | OpenAI gpt-4o-mini（支持第三方转发） |
| PDF 解析 | PyMuPDF |
| 认证 | JWT access + refresh token |
| 流式协议 | WebSocket |
| 包管理 | uv（后端）· bun（前端） |

---

## 快速开始

### 前置要求

- Python 3.11+，[uv](https://docs.astral.sh/uv/)
- Node.js 18+，[bun](https://bun.sh/)
- PostgreSQL 17 + pgvector 扩展

### 1. 克隆并配置环境

```bash
git clone https://github.com/rol1an/docuAI-RAG.git
cd docuAI-RAG
```

复制并填写后端配置：

```bash
cp backend/.env.example backend/.env
```

`.env` 关键配置项：

```bash
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=               # 第三方转发地址（可选）
AI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=你的数据库用户名
POSTGRES_PASSWORD=
POSTGRES_DB=docuai
```

### 2. 初始化数据库

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run docuai create-admin   # 创建管理员账号
```

### 3. 启动服务

```bash
# 后端（新终端）
uv run uvicorn app.main:app --reload --port 8000

# 前端（新终端）
cd frontend
bun install
bun dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端应用 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |

默认管理员账号：`admin@example.com` / `admin123`

---

## 使用流程

```
上传 PDF  →  自动入库（分块 + 向量化）  →  进入 Chat 页面  →  提问  →  流式回答 + Citation 卡片
```

### 文档管理

进入 **RAG** 页面上传文档，支持批量上传，上传后可在列表查看入库状态和 chunk 数量。

### CLI 工具

```bash
# 从命令行批量入库
uv run docuai rag-ingest /path/to/docs/ --collection documents --recursive

# 语义搜索测试
uv run docuai rag-search "your query" --collection documents

# 查看所有 collection
uv run docuai rag-collections
```

---

## 项目结构

```
docuAI-RAG/
├── backend/
│   └── app/
│       ├── api/routes/v1/    # HTTP + WebSocket 路由
│       ├── core/             # 配置、安全、异常
│       ├── db/               # 数据库模型与会话
│       ├── services/         # 业务逻辑
│       ├── repositories/     # 数据访问
│       ├── rag/              # RAG 核心
│       │   ├── pipeline.py   # 直接 RAG Pipeline（检索→构建 Prompt→流式输出）
│       │   ├── retrieval.py  # 向量检索 + 混合搜索 + 重排
│       │   ├── embeddings.py # Embedding 服务
│       │   ├── vectorstore.py# pgvector 向量存储
│       │   ├── ingestion.py  # 文档入库流程
│       │   └── reranker.py   # CrossEncoder 精排
│       └── agents/           # LangChain Agent（备用）
└── frontend/
    └── src/
        ├── app/              # Next.js App Router 页面
        ├── components/
        │   └── chat/         # 聊天组件（消息列表、Citation 卡片等）
        ├── hooks/            # useChat、useConversations 等
        ├── stores/           # Zustand 全局状态
        └── types/            # TypeScript 类型定义
```

---

## RAG Pipeline

本项目使用确定性的直接 RAG Pipeline，而非不稳定的 LangChain Agent：

```
用户提问
   ↓
向量检索（pgvector HNSW，Top-K）
   ↓
CrossEncoder 精排（可选，本地模型）
   ↓
构建 Prompt（系统提示 + 检索上下文 + 对话历史）
   ↓
LLM 流式输出（逐 Token via WebSocket）
   ↓
前端渲染 Markdown + Citation 卡片
```

**WebSocket 事件协议：**

```
retrieval_start  →  检索开始
citations        →  { citations: [...] }，检索完成，附带引用来源
text_delta       →  { content: "..." }，逐 Token 流式
final_result     →  { output: "..." }，完整文本
complete         →  { conversation_id: "..." }
```

---

## 开发命令

```bash
# 后端
cd backend
uv run uvicorn app.main:app --reload    # 启动开发服务器
uv run pytest tests/ -v                 # 运行测试
uv run ruff check app tests cli --fix   # 代码检查并修复
uv run ruff format app tests cli        # 代码格式化
uv run alembic revision --autogenerate -m "描述"  # 创建迁移
uv run alembic upgrade head             # 应用迁移

# 前端
cd frontend
bun dev              # 启动开发服务器
bun run lint         # ESLint 检查
bun run type-check   # TypeScript 类型检查
bun run test         # 运行单元测试
bun run build        # 构建生产版本
```

---

## License

MIT
