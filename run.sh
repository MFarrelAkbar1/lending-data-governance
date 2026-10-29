#!/usr/bin/env bash
# One command per pipeline stage. The Makefile calls these; on Windows without
# make, run them directly from Git Bash: ./run.sh all
set -euo pipefail
cd "$(dirname "$0")"

# Use the project virtualenv when it exists, otherwise whatever is on PATH.
if [ -x .venv/Scripts/python ]; then BIN="$PWD/.venv/Scripts/"
elif [ -x .venv/bin/python ]; then BIN="$PWD/.venv/bin/"
else BIN=""; fi
PY="${BIN}python"
export DBT_PROFILES_DIR="$PWD/dbt_project"
export PYTHONPATH="$PWD"

dbt_cmd() {
    [ -d dbt_project/dbt_packages ] || [ "$1" = deps ] || (cd dbt_project && "${BIN}dbt" deps)
    (cd dbt_project && "${BIN}dbt" "$@")
}

# Wait up to 60s for Postgres (docker compose up -d returns before it accepts connections).
wait_db() {
    "$PY" -c "
import time
from common.db import get_engine
for _ in range(60):
    try:
        get_engine().connect().close(); break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('Postgres not reachable, is docker compose up?')
"
}

setup() {
    python -m venv .venv
    if [ -x .venv/Scripts/python ]; then BIN="$PWD/.venv/Scripts/"; else BIN="$PWD/.venv/bin/"; fi
    "${BIN}python" -m pip install --upgrade pip
    "${BIN}python" -m pip install -r requirements.txt
    dbt_cmd deps
}

load()    { wait_db; "$PY" -m ingestion.sample_and_load "$@"; }
profile() { "$PY" -m profiling.profile_report; }
build()   { dbt_cmd run --exclude tag:dq; }

test() {
    # Freshness first: it also writes run_results.json, which `dbt test` then overwrites.
    dbt_cmd source freshness --select source:raw || true
    local status=0
    dbt_cmd test --exclude tag:dq || status=$?
    # Collect results even when error-severity tests fail, then propagate the exit code.
    "$PY" -m reports.collect_dq_results
    return $status
}

scorecard() {
    dbt_cmd run --select tag:dq
    "$PY" -m reports.build_scorecard
}

docs()    { dbt_cmd docs generate; echo "Serve with: cd dbt_project && dbt docs serve --port 8081"; }
sources() { "$PY" dbt_project/scripts/generate_sources.py; }

all() {
    load
    profile
    build
    test
    scorecard
    docs
}

# Second and later runs: reload (new batch, new _loaded_at), rebuild, retest.
monitor() {
    load
    build
    test
    scorecard
}

stage="${1:-all}"
shift || true
case "$stage" in
    setup|load|profile|build|test|scorecard|docs|sources|all|monitor) "$stage" "$@" ;;
    *) echo "usage: ./run.sh {setup|load|profile|build|test|scorecard|docs|sources|all|monitor}"; exit 1 ;;
esac
