#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 🕯️  Misbah — run everything (backend API + Angular frontend)
#
#   ./run.sh                 boot backend (:8077) + frontend (:4200)
#   ./run.sh --install       (re)install backend + frontend deps first
#   ./run.sh --ml            also install the heavy ML/QLoRA stack (requirements-ml.txt)
#   ./run.sh --backend       backend only
#   ./run.sh --frontend      frontend only
#
# The API boots without the ML stack (heavy imports are lazy); chat & training
# return a clear 503 until requirements-ml.txt is installed. Ctrl-C stops both.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

CONDA_ENV="${MISBAH_CONDA_ENV:-base}"   # env that has torch + CUDA
BACKEND_PORT="${MISBAH_BACKEND_PORT:-8077}"
FRONTEND_PORT="${MISBAH_FRONTEND_PORT:-4200}"

DO_INSTALL=0; DO_ML=0; RUN_BACKEND=1; RUN_FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --install)  DO_INSTALL=1 ;;
    --ml)       DO_INSTALL=1; DO_ML=1 ;;
    --backend)  RUN_FRONTEND=0 ;;
    --frontend) RUN_BACKEND=0 ;;
    -h|--help)  sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

c() { printf '\033[1;36m›\033[0m %s\n' "$*"; }

# ── resolve the conda python (so we don't depend on `conda activate` in scripts)
CONDA_BASE="$(conda info --base 2>/dev/null || echo "$HOME/miniconda3")"
PY="$CONDA_BASE/envs/$CONDA_ENV/bin/python"
[ "$CONDA_ENV" = "base" ] && PY="$CONDA_BASE/bin/python"
[ -x "$PY" ] || { echo "python not found for conda env '$CONDA_ENV' at $PY" >&2; exit 1; }

# ── optional install ─────────────────────────────────────────────────────────
if [ "$DO_INSTALL" = 1 ]; then
  c "Installing backend API deps (conda env: $CONDA_ENV)"
  "$PY" -m pip install -r "$BACKEND/requirements.txt"
  if [ "$DO_ML" = 1 ]; then
    c "Installing ML/QLoRA stack (requirements-ml.txt)"
    "$PY" -m pip install -r "$BACKEND/requirements-ml.txt"
  fi
  if [ "$RUN_FRONTEND" = 1 ]; then
    c "Installing frontend deps (npm install)"
    ( cd "$FRONTEND" && npm install )
  fi
fi

# ── process management ───────────────────────────────────────────────────────
PIDS=()
cleanup() {
  c "Shutting down…"
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

if [ "$RUN_BACKEND" = 1 ]; then
  c "Backend  → http://localhost:$BACKEND_PORT  (uvicorn, env: $CONDA_ENV)"
  ( cd "$BACKEND" && exec "$PY" -m uvicorn app.main:app --port "$BACKEND_PORT" --reload ) &
  PIDS+=($!)
fi

if [ "$RUN_FRONTEND" = 1 ]; then
  [ -d "$FRONTEND/node_modules" ] || { c "node_modules missing — running npm install"; ( cd "$FRONTEND" && npm install ); }
  # ng serve runs without a TTY here; suppress the Angular CLI first-run analytics
  # prompt, which otherwise force-closes and kills the frontend on a fresh machine.
  export NG_CLI_ANALYTICS=false
  c "Frontend → http://localhost:$FRONTEND_PORT  (ng serve, proxies /api → :$BACKEND_PORT)"
  ( cd "$FRONTEND" && exec npm start -- --port "$FRONTEND_PORT" ) &
  PIDS+=($!)
fi

c "Up. Press Ctrl-C to stop."
wait
