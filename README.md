# ub-rag-core

最小可执行 FastAPI RAG 后端：Markdown 入库 → Chunking → Embedding → pgvector → 向量召回 → Reranker → 返回 Top-K。

- 框架：FastAPI + SQLAlchemy 2.0 (async) + Alembic
- 向量库：PostgreSQL + [pgvector](https://github.com/pgvector/pgvector)
- Embedding：`BAAI/bge-m3`（1024 维，中英多语）
- Reranker：`BAAI/bge-reranker-v2-m3`
- Chunking：基于 [`langchain-text-splitters`](https://pypi.org/project/langchain-text-splitters/) 的 Markdown 标题切分 + 滑窗切块（封装为独立 `ChunkingService`）

---

## 一、架构

```mermaid
flowchart TD
    md[Markdown 输入] --> Ingest["POST /api/v1/documents"]
    Ingest --> Chunk[ChunkingService]
    Chunk --> Embed[BGEEmbedder.embed_documents]
    Embed --> Store[(PostgreSQL + pgvector)]

    Q[Query] --> Search["POST /api/v1/search"]
    Search --> EmbedQ[BGEEmbedder.embed_query]
    EmbedQ --> Recall["pgvector cosine top_k"]
    Recall --> Rerank[BGEReranker]
    Rerank --> Resp[返回 rerank_top_k]
```

## 二、目录结构

```text
ub-rag-core/
├── pyproject.toml
├── Dockerfile                  # 多阶段构建（builder + runtime），非 root 运行
├── docker-compose.yml          # 本地: app + pgvector，全部变量从 .env 注入
├── docker-compose.prod.yml     # 生产: 仅 app，连云 RDS，资源限制 + 回环端口
├── .env.example                # 本地 / 通用变量模板
├── .env.prod.example           # 生产环境变量模板
├── Makefile                    # 一键命令（make help 查看全部）
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/0001_init.py
├── scripts/
│   └── entrypoint.sh           # 等 DB → alembic upgrade → uvicorn
├── src/
│   ├── main.py                 # FastAPI app, lifespan 加载模型/DB
│   ├── config.py               # pydantic-settings
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── schemas.py
│   │   └── routes/{documents,search}.py
│   ├── core/db.py              # async engine / session
│   ├── models/document.py      # Document / Chunk ORM
│   └── services/
│       ├── chunking/           # 独立 service: 接口 + Markdown 实现 + 门面
│       ├── embedding/bge.py
│       ├── reranker/bge.py
│       ├── vector_store/pgvector_store.py
│       ├── ingestion.py        # 入库编排
│       └── retrieval.py        # 检索编排
└── tests/
```

## 三、快速开始（本地一键起）

依赖：Docker + Docker Compose v2。首次构建会拉 PyTorch CPU + FlagEmbedding，耗时较久；首次启动还会从 HuggingFace 拉模型权重（~3GB），已配置 `HF_ENDPOINT=https://hf-mirror.com` 加速。

最简：

```bash
make up           # 自动创建 .env、构建镜像、起 db + app
make logs         # 跟随 app 日志，等待 "embedder ready" / "reranker ready"
```

或者用原生命令：

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f app
```

服务起来后：

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

入库一个 Markdown：

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "RAG 简介",
    "content": "# RAG 简介\n\n检索增强生成（Retrieval-Augmented Generation）是一种将外部知识库与 LLM 结合的范式。\n\n## 工作流程\n\n1. 文本切分\n2. 向量化\n3. 检索\n4. 重排\n5. 生成",
    "metadata": {"tag": "demo"}
  }'
```

检索：

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "RAG 是什么？", "top_k": 20, "rerank_top_k": 5}'
```

常用命令（更多见 `make help`）：

| 命令              | 说明                                          |
| ----------------- | --------------------------------------------- |
| `make up`         | 起完整本地 stack（app + pgvector）            |
| `make logs`       | 跟随 app 日志                                 |
| `make sh`         | 进 app 容器 shell                             |
| `make psql`       | 用 psql 进 pgvector                           |
| `make migrate`    | 手动跑 `alembic upgrade head`                 |
| `make test`       | 在容器里跑 pytest                             |
| `make down`       | 停服务（保留数据卷）                          |
| `make clean`      | 停服务 + 删数据卷（含模型缓存，谨慎使用）     |

## 四、本地开发（不用 Docker）

需要本地有一个开了 pgvector 扩展的 PostgreSQL，或起一个临时容器：

```bash
docker run -d --name pgvector \
  -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag -e POSTGRES_DB=rag \
  -p 5432:5432 pgvector/pgvector:pg16
```

然后：

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
# PyTorch CPU 单独装（避免拉 CUDA 包）：
pip install torch --index-url https://download.pytorch.org/whl/cpu

cp .env.example .env
alembic upgrade head
uvicorn src.main:app --reload
```

## 五、API 概览

| Method | Path                              | 说明 |
|--------|-----------------------------------|------|
| POST   | `/api/v1/documents`               | 入库一个 Markdown 文档（自动 chunk + embed + 存储） |
| GET    | `/api/v1/documents/{id}`          | 读取文档元信息 + 全部 chunk |
| DELETE | `/api/v1/documents/{id}`          | 级联删除文档与其 chunk |
| POST   | `/api/v1/search`                  | 向量召回 + Reranker，返回 top-k |
| GET    | `/health`                         | 检查 DB / 模型就绪状态 |

### `POST /api/v1/documents`

```json
{
  "title": "string",
  "content": "markdown string",
  "source": "optional string",
  "metadata": { "any": "json" }
}
```

返回：`{ "document_id": "...", "num_chunks": 7 }`

### `POST /api/v1/search`

```json
{
  "query": "string",
  "top_k": 20,
  "rerank_top_k": 5,
  "filters": { "tag": "demo" }
}
```

`filters` 走 `metadata @> filters` JSONB 包含匹配。返回：

```json
{
  "query": "...",
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "content": "...",
      "score": 0.91,
      "recall_score": 0.78,
      "metadata": { "h1": "RAG 简介" }
    }
  ]
}
```

## 六、配置（.env）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://rag:rag@localhost:5432/rag` | 必须用 `postgresql+asyncpg://` |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-m3` | HF 模型名 |
| `EMBEDDING_DIM` | `1024` | 与模型保持一致；改变需新建 schema |
| `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-v2-m3` | |
| `MODEL_CACHE_DIR` | `.model_cache` | 模型权重缓存目录（建议挂卷） |
| `HF_ENDPOINT` | — | 国内可设为 `https://hf-mirror.com` |
| `DEVICE` | `cpu` | `cpu` 或 `cuda` |
| `USE_FP16` | `false` | GPU 上启用 FP16 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `512` / `64` | Markdown 分块参数 |
| `DEFAULT_TOP_K` / `DEFAULT_RERANK_TOP_K` | `20` / `5` | 召回 / 重排数量 |
| `WORKERS` | `1` | uvicorn worker 数；每个 worker 各加载一份模型（5–6GB），增并发请优先横向扩多副本 |
| `RUN_MIGRATIONS` | `false`（生产）/ `true`（本地 compose） | 业务容器启动前是否自动 `alembic upgrade head`；多副本必须设 `false`，迁移走单独的一次性容器 |

### 镜像无状态特性

业务容器是**无状态 worker**：

- 持久化数据全部在外部 PostgreSQL，容器内不写任何业务文件
- `app.state` 上的 embedder / reranker 是只读模型对象，不算业务状态
- `/app/.model_cache` 是只读模型权重缓存，丢了重新下载即可（不影响业务），多副本可共享 NAS / PVC（ReadOnly）
- 可以放心横向扩展（k8s replicas、多机部署、SAE 多实例）

**启动副作用清单**（部署时需要规划）：

| 副作用 | 何时发生 | 多副本下的处理 |
| --- | --- | --- |
| 等待 DB 可达 | 每次启动 | 无影响，每个副本各自等 |
| 拉模型权重 | 缓存目录为空时 | 共享 NAS / 各自拉都行 |
| `alembic upgrade head` | `RUN_MIGRATIONS=true` 时 | **生产必须关掉**，由部署流水线用一次性容器跑 |

## 七、阿里云部署

适用于 ECS / SAE / ACK 容器形态。下面以最常见的 **ECS + RDS PostgreSQL + ACR** 为例，给出"docker compose"和"docker run"两种方式。

### 1. 准备 RDS PostgreSQL

1. 在控制台创建 **RDS PostgreSQL 16**（或 ≥ 14，pgvector 要求 ≥ 12）实例。
2. 创建账号 `rag` / 数据库 `rag`，记下内网域名（形如 `pgm-xxxxxxxx.pg.rds.aliyuncs.com`）。
3. 在「数据库管理」中执行：
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. 在「白名单」里加入 ECS 的内网网段。

### 2. 构建并推送镜像到 ACR

本机或 CI 上：

```bash
# 在 ACR 控制台创建命名空间和仓库（例如 registry.cn-hangzhou.aliyuncs.com/<ns>/ub-rag-core）
docker login --username=<ali_user> registry.cn-hangzhou.aliyuncs.com

# Makefile 一键构建并推送（tag 默认取 git short-sha）
make build-push \
    IMAGE_NAME=registry.cn-hangzhou.aliyuncs.com/<ns>/ub-rag-core \
    IMAGE_TAG=0.1.0
```

或裸命令：

```bash
docker build -t registry.cn-hangzhou.aliyuncs.com/<ns>/ub-rag-core:0.1.0 .
docker push registry.cn-hangzhou.aliyuncs.com/<ns>/ub-rag-core:0.1.0
```

### 3. 在 ECS 上部署（推荐：docker compose 生产配置）

业务容器无状态 + 默认 `RUN_MIGRATIONS=false`，标准部署是 **pull → 一次性容器迁移 → 起业务容器** 三步。

```bash
# 一次性准备
git clone <repo> /opt/ub-rag-core && cd /opt/ub-rag-core
cp .env.prod.example .env.prod
vim .env.prod                       # 填入 IMAGE_NAME / IMAGE_TAG / DATABASE_URL（指向 RDS）

mkdir -p /data/ub-rag-core/model-cache   # 与 .env.prod 中 MODEL_CACHE_HOST_DIR 对齐

# 登录 ACR
docker login registry.cn-hangzhou.aliyuncs.com

# 一键部署（pull + migrate + up）
make prod-deploy
make prod-logs                      # 跟随日志直到 ready
```

或者拆开手动跑：

```bash
make prod-pull                      # 拉新镜像
make prod-migrate                   # 起一次性容器跑 alembic upgrade head 后退出
make prod-up                        # 起业务容器（不会再跑迁移）
```

升级版本：

```bash
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=0.2.0/' .env.prod
make prod-deploy                    # pull 新版 → migrate（如有新迁移）→ 滚动起 app
```

`docker-compose.prod.yml` 默认把 8000 端口绑到 `127.0.0.1`，由前置 SLB / Nginx 代理出去；并配置了 4c/8G 的资源上限（按规格在 `.env.prod` 调）。模型缓存挂载到 `/data/ub-rag-core/model-cache`，重启秒级就绪。

### 4. 在 ECS 上部署（最简：docker run）

如果不想引入 compose，用 `docker run` 直接跑也行。同样**先迁移再起业务**：

```bash
IMG=registry.cn-hangzhou.aliyuncs.com/<ns>/ub-rag-core:0.1.0
DB_URL="postgresql+asyncpg://rag:<pwd>@pgm-xxx.pg.rds.aliyuncs.com:5432/rag"

docker pull $IMG

# Step 1: 一次性容器跑迁移（跑完即删）
docker run --rm \
  -e DATABASE_URL="$DB_URL" \
  $IMG alembic upgrade head

# Step 2: 起业务容器（无状态 worker）
docker run -d --name ub-rag-core \
  --restart=always \
  -p 127.0.0.1:8000:8000 \
  -v /data/ub-rag-core/model-cache:/app/.model_cache \
  --memory=8g --cpus=4 \
  -e DATABASE_URL="$DB_URL" \
  -e MODEL_CACHE_DIR=/app/.model_cache \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e DEVICE=cpu \
  -e USE_FP16=false \
  -e WORKERS=1 \
  -e RUN_MIGRATIONS=false \
  $IMG
```

> 把 `alembic upgrade head` 直接作为 `docker run` 的命令传入，会被入口识别为「一次性任务」，跳过启动应用、跑完直接退出。

### 5. SAE / ACK 提示

- **SAE**：直接使用上面的 ACR 镜像；环境变量参考 `.env.prod.example`，**`RUN_MIGRATIONS=false` 必须设**；建议挂载 NAS 作为模型缓存盘；CPU 4c8g 起步（BGE-M3 + Reranker 内存约 5–6GB）。迁移用「定时任务/Job」类型再启一个一次性容器执行 `alembic upgrade head`。
- **ACK**：
  - 业务用 Deployment（多副本无状态），`RUN_MIGRATIONS=false`
  - 迁移用 Job，`command: ["alembic", "upgrade", "head"]`，部署流水线里安排在 Deployment rollout 之前
  - 模型缓存用 PVC（多副本可 ReadOnlyMany 共享）
  - 加 `livenessProbe`/`readinessProbe` 指向 `/health`；模型加载较慢，`initialDelaySeconds` 设 120s
  - 镜像内置的 `HEALTHCHECK` 在 K8s 下被忽略，仍需在 manifest 里配探针

### 6. 安全组 / VPC / 网关提示

- ECS / SAE / ACK 与 RDS 必须在同一 VPC 或可达；RDS 白名单放通对应私网网段。
- 镜像内置非 root 用户（uid=1000）和 `tini` 作为 PID 1，信号转发与僵尸回收已处理好。
- 对外暴露 8000 端口前建议加 SLB / WAF / 鉴权层；本仓库未内置鉴权。

## 八、测试

仅本地无依赖单元测试（chunking / schemas）：

```bash
pip install -e '.[dev]'
pytest -q
```

涉及 DB / 模型的集成测试可以在 `docker compose up` 之后通过 `curl` / `httpx` 实际打 API 验证。

## 九、后续可扩展点

- 替换 chunker：实现 `Chunker` Protocol 注入到 `ChunkingService`，无需改 ingestion / API。
- 替换 embedder / reranker：实现 `Embedder` / `Reranker` Protocol，main lifespan 中替换即可。
- 扩展为微服务：把 `services/chunking` 抽出为独立 FastAPI 进程，`ChunkingService` 改为 HTTP 客户端，调用方零改动。
- 加 BM25 / hybrid search：在 `chunks` 上加 `tsvector` 列与 GIN 索引，retrieval 中融合两路得分再 rerank。
- 加鉴权与多租户：在 `Document` 上加 `tenant_id`，`metadata @>` 过滤已自动支持。
