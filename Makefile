# =============================================================================
# 常用命令一键化封装。
# 用法：
#   make help          查看所有命令
#   make up            本地起完整 stack（app + pgvector）
#   make logs          跟随 app 日志
#   make sh            进 app 容器 shell
#   make migrate       手动跑一次迁移
#   make build         构建生产镜像
#   make push          推送到镜像仓库
#   make prod-deploy   在生产机上 pull + 起服务（前提：已配置 .env.prod）
# =============================================================================

SHELL          := /usr/bin/env bash

# 镜像名 / tag。可在命令行覆盖：make build IMAGE_TAG=v0.2.0
IMAGE_NAME     ?= ub-rag-core
IMAGE_TAG      ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")
IMAGE          := $(IMAGE_NAME):$(IMAGE_TAG)

# Compose 文件
COMPOSE        := docker compose
COMPOSE_DEV    := $(COMPOSE) -f docker-compose.yml
COMPOSE_PROD   := $(COMPOSE) -f docker-compose.prod.yml --env-file .env.prod

.DEFAULT_GOAL  := help

# -----------------------------------------------------------------------------
# Meta
# -----------------------------------------------------------------------------
.PHONY: help
help: ## 显示所有可用命令
	@awk 'BEGIN{FS=":.*##"; printf "\n可用命令:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# -----------------------------------------------------------------------------
# 本地开发（docker-compose）
# -----------------------------------------------------------------------------
.PHONY: env
env: ## 若没有 .env，从 .env.example 复制一份
	@test -f .env || (cp .env.example .env && echo "[make] .env created from .env.example")

.PHONY: up
up: env ## 启动完整本地 stack（app + pgvector），后台运行
	$(COMPOSE_DEV) up -d --build

.PHONY: down
down: ## 停止并移除容器（保留数据卷）
	$(COMPOSE_DEV) down

.PHONY: clean
clean: ## 停止并移除容器 + 数据卷（含模型缓存，谨慎使用）
	$(COMPOSE_DEV) down -v

.PHONY: restart
restart: ## 重启 app 服务
	$(COMPOSE_DEV) restart app

.PHONY: logs
logs: ## 跟随 app 日志
	$(COMPOSE_DEV) logs -f app

.PHONY: logs-db
logs-db: ## 跟随 db 日志
	$(COMPOSE_DEV) logs -f db

.PHONY: ps
ps: ## 查看服务状态
	$(COMPOSE_DEV) ps

.PHONY: sh
sh: ## 进入 app 容器 shell
	$(COMPOSE_DEV) exec app /bin/bash

.PHONY: psql
psql: ## 用 psql 进 pgvector 数据库
	$(COMPOSE_DEV) exec db psql -U $${POSTGRES_USER:-rag} -d $${POSTGRES_DB:-rag}

.PHONY: migrate
migrate: ## 一次性容器跑 alembic upgrade head（不需要 app 已经在跑）
	$(COMPOSE_DEV) run --rm app alembic upgrade head

.PHONY: migrate-status
migrate-status: ## 查看当前迁移版本
	$(COMPOSE_DEV) run --rm app alembic current

.PHONY: makemigration
makemigration: ## 生成新的 alembic 迁移：make makemigration MSG="add xxx"
	@test -n "$(MSG)" || (echo "请通过 MSG=\"...\" 提供迁移说明" && exit 1)
	$(COMPOSE_DEV) run --rm app alembic revision --autogenerate -m "$(MSG)"

.PHONY: test
test: ## 在 app 容器里跑 pytest
	$(COMPOSE_DEV) exec app pytest -q

# -----------------------------------------------------------------------------
# 镜像构建 / 推送
# -----------------------------------------------------------------------------
.PHONY: build
build: ## 构建生产镜像（使用 git short-sha 作为默认 tag）
	docker build -t $(IMAGE) -t $(IMAGE_NAME):latest .
	@echo "[make] built $(IMAGE)"

.PHONY: push
push: ## 推送镜像到仓库（需要先 docker login）
	docker push $(IMAGE)
	docker push $(IMAGE_NAME):latest

.PHONY: build-push
build-push: build push ## 构建并推送

# -----------------------------------------------------------------------------
# 生产部署（在已配置好 .env.prod 的机器上执行）
# -----------------------------------------------------------------------------
.PHONY: prod-pull
prod-pull: ## 拉取最新镜像
	$(COMPOSE_PROD) pull

.PHONY: prod-migrate
prod-migrate: ## 在生产环境跑一次性迁移容器（推荐：部署前先调一次）
	$(COMPOSE_PROD) run --rm app alembic upgrade head

.PHONY: prod-migrate-status
prod-migrate-status: ## 查看生产 DB 当前迁移版本
	$(COMPOSE_PROD) run --rm app alembic current

.PHONY: prod-up
prod-up: ## 起生产业务容器（不会自动迁移，建议先跑 prod-migrate）
	$(COMPOSE_PROD) up -d

.PHONY: prod-down
prod-down: ## 停掉生产业务容器
	$(COMPOSE_PROD) down

.PHONY: prod-logs
prod-logs: ## 跟随生产 app 日志
	$(COMPOSE_PROD) logs -f app

.PHONY: prod-deploy
prod-deploy: prod-pull prod-migrate prod-up ## 标准部署流程：pull → migrate（一次性）→ up
	@echo ""
	@echo "[make] 部署完成。用 'make prod-logs' 跟随日志确认 ready。"

.PHONY: prod-shell
prod-shell: ## 在生产环境起一次性容器跑任意命令：make prod-shell CMD="python -V"
	@test -n "$(CMD)" || (echo "请通过 CMD=\"...\" 提供命令" && exit 1)
	$(COMPOSE_PROD) run --rm app $(CMD)
