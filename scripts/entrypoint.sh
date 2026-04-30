#!/usr/bin/env bash
# =============================================================================
# 容器入口。两种使用方式：
#
# 1) 业务进程（默认）：
#    docker run <image>                            # 用 WORKERS 控制并发
#    docker run -e WORKERS=2 <image>
#
# 2) 一次性任务（不会启动应用，直接 exec 你给的命令然后退出）：
#    docker run --rm <image> alembic upgrade head
#    docker run --rm <image> alembic downgrade -1
#    docker run --rm <image> python -m scripts.something
#
# 入口逻辑：
#   - 始终等待 DATABASE_URL 可达（前提是设置了）
#   - RUN_MIGRATIONS=true 时启动前自动跑一次迁移（默认 false，多副本场景请用方式 2）
#   - 没有显式传命令 → 启动 uvicorn（用 WORKERS / HOST / PORT 环境变量）
#   - 显式传命令 → 原样 exec
# =============================================================================
set -euo pipefail

log() { echo "[entrypoint] $*"; }

# ---------- 1. 等待数据库 ----------
if [[ -n "${DATABASE_URL:-}" ]]; then
  log "waiting for database to be reachable..."
  python - <<'PY'
import os
import re
import socket
import time

url = os.environ["DATABASE_URL"]
m = re.match(r".*://(?:[^:]+:[^@]+@)?([^:/]+)(?::(\d+))?", url)
if not m:
    raise SystemExit(f"cannot parse DATABASE_URL host: {url}")
host = m.group(1)
port = int(m.group(2) or 5432)

deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] db reachable at {host}:{port}")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"database unreachable at {host}:{port} after 60s")
PY
fi

# ---------- 2. 一次性任务模式 ----------
# 如果调用方显式传了命令（compose run / docker run <image> CMD ARGS...），
# 直接 exec，不启动应用、不跑自动迁移。
# 判定规则：第一个参数不是 uvicorn / 不是空。
if [[ $# -gt 0 && "$1" != "uvicorn" ]]; then
  log "one-shot task: $*"
  exec "$@"
fi

# ---------- 3. 业务进程模式 ----------
# 可选自动迁移（默认关闭，避免多副本竞争）。
if [[ "${RUN_MIGRATIONS:-false}" == "true" ]]; then
  log "RUN_MIGRATIONS=true, running 'alembic upgrade head' before start..."
  log "WARNING: don't enable this on multi-replica deployments. Run migrations as a separate one-shot task instead."
  alembic upgrade head
else
  log "RUN_MIGRATIONS=false, skipping. Make sure migrations have been applied externally."
fi

# uvicorn 参数从环境变量读，默认单 worker。
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"

log "starting uvicorn: host=${HOST} port=${PORT} workers=${WORKERS}"
exec uvicorn src.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}"
