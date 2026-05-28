# Hiiv — common tasks (works with GNU Make: macOS, Linux, Git Bash on Windows)
# Windows without `make`: from repo root in PowerShell use .\dev-api.cmd and .\dev-web.cmd
# (PowerShell requires .\ to run a script in the current directory.)
.PHONY: help install install-api install-web dev-api dev-web build-web lint-web docker-up docker-down

help:
	@echo "Hiiv targets:"
	@echo "  make install      - Install Python + Node dependencies"
	@echo "  make install-api  - pip install (apps/api)"
	@echo "  make install-web  - npm install (apps/web)"
	@echo "  make dev-api      - Run FastAPI on :8000 (from apps/api)"
	@echo "  make dev-web      - Run Next.js dev on :3000 (from apps/web)"
	@echo "  make build-web    - Production build for apps/web"
	@echo "  make lint-web     - ESLint for apps/web"
	@echo "  make docker-up    - docker compose up --build"
	@echo "  make docker-down  - docker compose down"
	@echo ""
	@echo "Use two terminals: make dev-api  |  make dev-web"
	@echo "Windows PowerShell (no make): .\\dev-api.cmd  |  .\\dev-web.cmd"

install: install-api install-web

install-api:
	cd apps/api && pip install -r requirements.txt

install-web:
	cd apps/web && npm install

dev-api:
	cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd apps/web && npm run dev

build-web:
	cd apps/web && npm run build

lint-web:
	cd apps/web && npm run lint

docker-up:
	docker compose up --build

docker-down:
	docker compose down
