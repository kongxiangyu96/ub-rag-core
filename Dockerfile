# syntax=docker/dockerfile:1.7

# =========================================================
# Stage 1: builder — 安装依赖到独立 venv，便于在 runtime 阶段直接拷贝
# =========================================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 用独立 venv 让最终镜像可以一行 COPY 拿走所有依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build

# 先只拷贝依赖描述文件，最大化利用 docker 层缓存：
# 只要 pyproject.toml 不变，下面这一层就能复用，避免每次代码改动都重装 PyTorch / FlagEmbedding。
COPY pyproject.toml README.md ./

# 单独装 CPU 版 PyTorch（FlagEmbedding 依赖 torch；从默认源装会拉 CUDA 包，体积巨大）
RUN pip install --upgrade pip wheel \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch

# 安装项目自身依赖（不含项目代码）
RUN mkdir -p src && touch src/__init__.py \
    && pip install . \
    && rm -rf src

# =========================================================
# Stage 2: runtime — 只保留运行时所需，最小化镜像体积
# =========================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HF_HOME=/app/.model_cache \
    MODEL_CACHE_DIR=/app/.model_cache

# 运行时只需要 libpq5（asyncpg/psycopg 依赖）和 curl（HEALTHCHECK 用）
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 app \
    && useradd  --system --uid 1000 --gid app --home /app --shell /usr/sbin/nologin app

# 拷贝 builder 中已经装好的 venv
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# 项目代码（变动最频繁，放最后让上面所有层都能命中缓存）
COPY --chown=app:app pyproject.toml README.md alembic.ini ./
COPY --chown=app:app src ./src
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app scripts ./scripts

RUN mkdir -p /app/.model_cache \
    && chown -R app:app /app \
    && chmod +x /app/scripts/entrypoint.sh

USER app

EXPOSE 8000

# 容器自身的健康检查（compose / k8s 也可以再加一层探针）
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# 用 tini 做 PID 1，正确转发信号、回收僵尸进程
ENTRYPOINT ["/usr/bin/tini", "--", "/app/scripts/entrypoint.sh"]

# 默认启动业务进程（uvicorn）。worker 数 / host / port 由 entrypoint 读 WORKERS / HOST / PORT 环境变量决定。
# 一次性任务请直接传命令覆盖，例如：
#   docker run --rm <image> alembic upgrade head
CMD []
