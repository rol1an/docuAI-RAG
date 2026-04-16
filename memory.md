# docuAI 项目概述与阶段记录

docuAI 是一个文档问答 AI 应用，支持上传 PDF 文档后进行语义检索问答，核心体验是流式回答 + Citations 高亮引用。

项目主目录：/Users/luojian/claudecode/docuAI/
骨架代码目录：/Users/luojian/claudecode/docuAI/docuai/
结构文档：/Users/luojian/claudecode/docuAI/PROJECT_STRUCTURE.md

---

## 技术栈

| 层次 | 技术选型 |
|------|---------|
| 前端框架 | Next.js 15 (App Router) |
| 前端 UI | Tailwind CSS + shadcn/ui (Radix) |
| 前端状态 | Zustand（全局）+ TanStack Query（服务端状态） |
| 后端框架 | FastAPI + Pydantic v2 |
| 数据库 ORM | SQLAlchemy 2.0 async |
| 数据库 | PostgreSQL 17 + pgvector 0.8.2 |
| 向量索引 | HNSW（pgvector 内置） |
| Embedding | OpenAI text-embedding-3-small（1536 维） |
| LLM | OpenAI gpt-4o-mini（.env 中 AI_MODEL，第三方转发） |
| RAG 框架 | LangChain（分块/Loader） |
| Reranker | sentence-transformers CrossEncoder (cross-encoder/ms-marco-MiniLM-L6-v2) |
| PDF 解析 | PyMuPDF |
| 认证 | JWT（access + refresh，7天） |
| 流式协议 | SSE（Server-Sent Events） |
| 迁移工具 | Alembic |
| 包管理 | uv（后端）+ bun（前端） |
| Python 环境 | conda env docuAI，Python 3.11.15 |

---

## 环境信息

- conda 环境：docuAI，路径 /opt/anaconda3/envs/docuAI/
- PostgreSQL 17 via Homebrew，brew services start postgresql@17，端口 5432
- pgvector 0.8.2 已安装（注意：pgvector homebrew 包只支持 pg17/18，不支持 pg16）
- DB 用户：luojian（系统用户，无密码），DB 名：docuai
- VIRTUAL_ENV warning 可忽略（是当前目录 .venv 干扰，不影响运行）

### 启动命令

```bash
# PostgreSQL（如未运行）
brew services start postgresql@17

# 后端
cd /Users/luojian/claudecode/docuAI/docuai
uv run --directory backend docuai server run --reload

# 前端（新终端）
cd /Users/luojian/claudecode/docuAI/docuai/frontend
bun dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |

### 管理员账号

- Email: admin@example.com
- Password: admin123

---

## 后端三层架构

Routes（只做HTTP/验证）→ Services（业务逻辑）→ Repositories（数据访问）

- api/routes/ — 只处理 HTTP、参数校验、调 Service，不含业务逻辑
- services/ — 编排完整业务流（document_service 负责上传→解析→向量化全流程）
- repositories/ — 只写数据库操作，不知道业务逻辑

依赖注入用 Annotated 别名（deps.py），路由里不写裸 Depends()。

Domain Exception 独立定义（core/exceptions.py），通过 exception_handler 映射到 HTTP 状态码。

---

## 骨架生成方式

用 fastapi-fullstack CLI（安装在 docuAI conda 环境）生成：

```bash
/opt/anaconda3/envs/docuAI/bin/fastapi-fullstack create docuai \
  --database postgresql \
  --ai-framework langchain \
  --llm-provider openai \
  --rag \
  --vector-store pgvector \
  --reranker cross_encoder \
  --pdf-parser pymupdf \
  --frontend nextjs \
  --python-version 3.11 \
  --output /Users/luojian/claudecode/docuAI
```

---

## 已修复的 Bug（Session 1）

backend/app/rag/vectorstore.py:136 — f-string 中 '{}'::jsonb 被 Python 解析器误判为空表达式。

修复方式：将字面量抽出为变量再插入 f-string：

```python
empty_json = "'{}'"
await session.execute(text(f"... metadata JSONB DEFAULT {empty_json}::jsonb ..."))
```

向量表名称冲突 — _table("documents") 原本返回 rag_documents，与 Alembic 迁移表重名。

修复方式：将前缀从 rag_ 改为 vec_：

```python
def _table(self, name: str) -> str:
    return f"vec_{_validate_collection_name(name)}"
```

---

## 已修复的 Bug（Session 2）

### 1) 第三方 OpenAI API 配置

第三方转发地址：https://api.shubiaobiao.com/v1

backend/app/core/config.py — 添加 OPENAI_BASE_URL 字段：

```python
OPENAI_API_KEY: str = ""
OPENAI_BASE_URL: str | None = None
AI_MODEL: str = "gpt-4o-mini"
```

backend/app/agents/langchain_assistant.py — 传入 base_url 到 ChatOpenAI，修复 get_agent() 签名：

```python
model = ChatOpenAI(
    model=self.model_name,
    temperature=self.temperature,
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL or None,
)

def get_agent(model_name: str | None = None) -> LangChainAssistant:
    return LangChainAssistant(model_name=model_name)
```

backend/app/rag/embeddings.py — OpenAI client 使用 settings 中的 key 和 base_url：

```python
from app.core.config import settings
self.client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL or None,
)
```

backend/.env 关键配置（敏感信息已脱敏）：

```env
OPENAI_API_KEY=<REDACTED>
OPENAI_BASE_URL=https://api.shubiaobiao.com/v1
AI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
POSTGRES_USER=luojian
POSTGRES_PASSWORD=
```

### 2) RAG 上传流程完整 Bug 链修复

backend/app/api/routes/v1/rag.py — 三个 background task 函数之前调用 IngestionService() 时缺少必需参数。修复为手动构造完整依赖链，并回填 vector_document_id/chunk_count。

backend/app/rag/models.py — IngestionResult 添加 chunk_count 字段。

backend/app/rag/ingestion.py — 计算并返回 chunk_count。

### 3) 前端嵌套 button 修复

frontend/src/app/[locale]/(dashboard)/rag/page.tsx — collection 列表项内删除按钮由内层 button 改为 div role=button，修复不合法嵌套。

---

## 数据库表（已迁移）

迁移文件：backend/alembic/versions/2026-04-15_initial.py

已创建表：users, conversations, messages, rag_documents, chat_files, tool_calls, sync_sources, sync_logs

- messages 表含 citations JSONB 字段，历史对话可复原高亮
- rag_documents 表含 collection_name 字段，支持多集合隔离

注意：向量表由 rag/vectorstore.py 在运行时动态创建（_ensure_collection），不在 Alembic 迁移中，命名为 vec_{collection_name}（默认 collection: documents）。

---

## RAG 配置（.env）

```env
RAG_DEFAULT_COLLECTION=documents
RAG_TOP_K=10
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50
RAG_CHUNKING_STRATEGY=recursive
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L6-v2
EMBEDDING_MODEL=text-embedding-3-small
AI_MODEL=gpt-4o-mini
```

RAG 两阶段检索：pgvector 余弦相似度粗召回 Top-K → CrossEncoder 精排。

---

## 端到端验证结果

- Attention is all u need.pdf（2.2MB）成功入库，114 个 chunk，status: done
- 第三方 API 连通性已通过 curl 验证
- 前端 RAG 页面可访问，上传按钮功能正常
- RAG Pipeline 端到端验证通过（提问 attention mechanism，正确检索并流式回答，带 citations）

---

## 已修复的 Bug（Session 3）

### 1) Chat 替换为直接 RAG Pipeline

废弃：LangChain Agent（不稳定，不一定调用 search 工具）

新建 backend/app/rag/pipeline.py，RAGPipeline.stream() 顺序产出：
- retrieval_start
- citations
- token（逐 token 流式）
- done（full_text）

修改 backend/app/api/routes/v1/agent.py：
- 移除 LangChain Agent 导入及 build_message_history()
- 新增 _get_rag_pipeline() 工厂函数（手动构造依赖链）
- WebSocket handler 迭代 pipeline.stream() 并映射 citations/text_delta/final_result/complete

### 2) Citation 去重 Bug 修复

问题根因：chunk_num 每页重置 + 同文档重复入库导致重复引用。

修复：
- retrieval.py 去重 key 改为 parent_doc_id + page_num + chunk_num + content_hash
- pipeline.py _build_citations() 按内容前 120 字符去重
- 清理重复向量文档数据

### 3) Citation 前端展示

新增 frontend/src/components/chat/citation-card.tsx。

修改：
- frontend/src/types/chat.ts：新增 Citation 接口与 WSEventType.citations
- frontend/src/hooks/use-chat.ts：处理 citations 事件
- frontend/src/components/chat/message-item.tsx：渲染 CitationList

---

## 已修复的 Bug（Session 4，近期新增）

### 1) 历史聊天记录无法加载

问题：点击侧边栏历史会话后消息不显示。

修复：
- 将历史消息加载后直接 hydrate 到可见聊天状态（chat store）
- 移除易失效的中间同步桥接逻辑
- 结果：历史会话稳定显示

### 2) 聊天检索阶段静默等待

问题：发送消息后 5-15 秒无状态反馈。

修复：
- 新增 processingPhase: idle/searching/responding
- 在 searching 阶段展示检索中提示
- 结果：用户可感知检索进度

### 3) Citation 持久化缺失导致历史引文卡片丢失

问题：实时会话里有 citations，历史会话丢失。

修复链路：
- backend Message 模型/Schema 增加 citations 字段
- WebSocket assistant 持久化时写入 citations
- 前端 conversation 类型与历史 hydration 增加 citations 映射
- 新增服务层回归测试覆盖 citations 透传

结果：历史对话可恢复引文卡片。

### 4) 测试基线修复与全量通过

问题：tests/test_agents.py 默认 prompt 断言与当前 RAG prompt 不一致。

修复：将测试期望更新为 get_system_prompt_with_rag()。

结果：
- 后端全量测试通过：187 passed
- conversation 服务测试通过

### 5) 文档上传后前端未正确显示已入库文档

问题：上传后前端列表更新滞后，processing 到 done 过渡不稳定。

修复：
- 文档页增加 processing 状态自动轮询刷新（3 秒）
- done 状态显示 chunk_count，提高入库可见性
- 新增手动 Refresh 按钮，支持强制重拉

结果：上传后文档状态可自动/手动刷新到 done，显示已入库。

---

## Citation 数据结构（已实现）

```typescript
interface Citation {
  doc_id: string;
  filename: string;
  page_number: number | null;
  text_snippet: string;
  score: number;
}
```

WebSocket 事件协议（实际使用）：
- type: retrieval_start
- type: citations, data: { citations: Citation[] }
- type: text_delta, data: { content: "..." }
- type: final_result, data: { output: "..." }
- type: complete, data: { conversation_id: "..." }

---

## 当前进度

- [x] 架构设计与技术选型确定
- [x] 完整目录结构起草（PROJECT_STRUCTURE.md）
- [x] conda 环境 docuAI 创建（Python 3.11）
- [x] fastapi-fullstack 安装并验证
- [x] 项目骨架生成（backend + frontend）
- [x] PostgreSQL 17 + pgvector 安装配置
- [x] 数据库迁移执行（8 张表）
- [x] 后端启动验证（health/live + health/ready）
- [x] 前端启动验证（localhost:3000）
- [x] 管理员账号创建 + JWT 登录验证
- [x] vectorstore.py f-string bug 修复
- [x] 向量表前缀修复（vec_ 替代 rag_）
- [x] 第三方 OpenAI API 配置（base_url 透传到 config/agent/embeddings）
- [x] get_agent() model_name 参数修复
- [x] RAG 路由 IngestionService 构造修复（3处 background task）
- [x] IngestionResult.chunk_count 字段添加并全链路传递
- [x] 前端 RAG 页面嵌套 button 修复
- [x] 端到端 PDF 入库验证（114 chunks）
- [x] Chat 替换为直接 RAG Pipeline
- [x] Citation 去重修复
- [x] Citation 前端展示
- [x] 历史对话记录点击无法加载（已修复）
- [x] 文档上传后前端正确显示已入库文档（已修复）
- [ ] Reranker 离线问题（cross-encoder 模型需本地缓存）

---

## 维护建议

- 将敏感配置（API Key）仅存放在 .env，不写入文档仓库。
- 每次修复后同步更新本文件中的 当前进度 与 会话修复章节，避免状态漂移。
- 若后续引入离线模式，优先补齐 reranker 模型缓存策略与启动自检。
