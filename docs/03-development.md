# Development

## Deep dives

- [Testing guide](testing/README.md)
- [Troubleshooting deep dive](troubleshooting/README.md)

This page describes the **canonical contributor workflow** for Mission Control, including local dev loops and CI parity.

> Evidence basis: consolidated from repo root `README.md`, `.github/workflows/ci.yml`, `Makefile`, `scripts/with_node.sh`, and `docs/testing/README.md`.

## Prerequisites

- Docker + Docker Compose v2 (`docker compose`)
- Python **3.12+** + `uv`
- Node.js + npm
  - CI pins **Node 20** via GitHub Actions (`actions/setup-node@v4` with `node-version: "20"`).

## Repo structure (where to run commands)

- Repo root: `Makefile` contains canonical targets.
- Backend code: `backend/` (FastAPI)
- Frontend code: `frontend/` (Next.js)

## “One command” setup

From repo root:

```bash
make setup
```

What it does:
- Syncs backend deps with `uv`.
- Syncs frontend deps with `npm` via the node wrapper.

## Canonical checks (CI parity)

### Run everything locally (closest to CI)

From repo root:

```bash
make check
```

CI runs two jobs:
- `check` (lint/typecheck/tests/coverage/build)
- `e2e` (Cypress)

## Backend workflow

### Install/sync deps

```bash
cd backend
uv sync --extra dev
```

### Run the API (dev)

```bash
cd backend
cp .env.example .env
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Backend checks

From repo root:

```bash
make backend-lint       # flake8
make backend-typecheck  # mypy --strict
make backend-test       # pytest
make backend-coverage   # pytest + scoped coverage gate
```

### DB migrations

From repo root:

```bash
make backend-migrate
```

## Frontend workflow

### Install deps

```bash
cd frontend
npm install
```

(or from repo root: `make frontend-sync`)

### Run the UI (dev)

```bash
cd frontend
cp .env.example .env.local
# Ensure NEXT_PUBLIC_API_URL is correct for the browser:
# NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

### Frontend checks

From repo root:

```bash
make frontend-lint       # eslint
make frontend-typecheck  # tsc
make frontend-test       # vitest
make frontend-build      # next build
```

## Local dev loops

### Loop A (recommended): DB via Compose, backend + frontend in dev mode

1) Start Postgres only:

```bash
cp .env.example .env
docker compose -f compose.yml --env-file .env up -d db
```

2) Backend (local):

```bash
cd backend
cp .env.example .env
uv sync --extra dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3) Frontend (local):

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

### Loop B: all-in-one Docker Compose

```bash
cp .env.example .env

docker compose -f compose.yml --env-file .env up -d --build
```

Useful ops:

```bash
docker compose -f compose.yml --env-file .env logs -f --tail=200
docker compose -f compose.yml --env-file .env up -d --build backend
# destructive reset (drops Postgres volume):
docker compose -f compose.yml --env-file .env down -v
```

## Cypress E2E workflow (high level)

See the deep dive: [docs/testing/README.md](testing/README.md).

Notes:
- E2E uses Clerk (official `@clerk/testing` integration); CI injects Clerk env vars.

## Tooling notes

### Node wrapper (`scripts/with_node.sh`)

Many Make targets run frontend commands via `bash scripts/with_node.sh`.
It checks `node`/`npm`/`npx` and can use `nvm` if present.

## Quick troubleshooting

- UI loads but API calls fail / activity feed blank:
  - confirm `NEXT_PUBLIC_API_URL` is set and browser-reachable.
  - see [Troubleshooting](troubleshooting/README.md).
