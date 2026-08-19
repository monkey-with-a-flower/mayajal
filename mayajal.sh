#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$ROOT_DIR/.mayajal"
RUN_DIR="$STATE_DIR/run"
LOG_DIR="$STATE_DIR/logs"
TELEMETRY_FILE="$ROOT_DIR/assets/telemetry_compose.yml"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LABEL="com.mayajal.backend"
FRONTEND_LABEL="com.mayajal.frontend"

mkdir -p "$RUN_DIR" "$LOG_DIR"

say() { printf '%s\n' "$*"; }
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Required command '$1' is not installed."; }

pid_alive() {
  local pid_file="$1" pid
  [[ -f "$pid_file" ]] || return 1
  pid="$(<"$pid_file")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

wait_http() {
  local name="$1" url="$2" attempts="${3:-60}" count
  for ((count=1; count<=attempts; count++)); do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      say "✓ $name"
      return 0
    fi
    sleep 1
  done
  say "✗ $name ($url)"
  return 1
}

start_backend() {
  if curl -fsS --max-time 2 http://127.0.0.1:8001/health >/dev/null 2>&1; then
    say "Backend is already available on port 8001."
    return
  fi
  if [[ -x "$ROOT_DIR/api_test/.venv/bin/uvicorn" ]]; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      launchctl remove "$BACKEND_LABEL" >/dev/null 2>&1 || true
      launchctl submit -l "$BACKEND_LABEL" -o "$LOG_DIR/backend.log" -e "$LOG_DIR/backend.log" -- \
        /bin/bash -c "cd \"$ROOT_DIR\" && exec api_test/.venv/bin/uvicorn api_test.main:app --host 0.0.0.0 --port 8001"
      return
    fi
    (
      cd "$ROOT_DIR"
      nohup api_test/.venv/bin/uvicorn api_test.main:app --host 0.0.0.0 --port 8001 </dev/null >"$LOG_DIR/backend.log" 2>&1 &
      echo $! >"$BACKEND_PID_FILE"
    )
  elif command -v uv >/dev/null 2>&1; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      launchctl remove "$BACKEND_LABEL" >/dev/null 2>&1 || true
      launchctl submit -l "$BACKEND_LABEL" -o "$LOG_DIR/backend.log" -e "$LOG_DIR/backend.log" -- \
        /bin/bash -c "cd \"$ROOT_DIR\" && exec uv run --project api_test uvicorn api_test.main:app --host 0.0.0.0 --port 8001"
      return
    fi
    (
      cd "$ROOT_DIR"
      nohup uv run --project api_test uvicorn api_test.main:app --host 0.0.0.0 --port 8001 </dev/null >"$LOG_DIR/backend.log" 2>&1 &
      echo $! >"$BACKEND_PID_FILE"
    )
  else
    fail "Backend environment is unavailable. Create api_test/.venv or install uv."
  fi
}

start_frontend() {
  local node_bin
  if curl -fsS --max-time 2 http://127.0.0.1:3000 >/dev/null 2>&1; then
    say "Frontend is already available on port 3000."
    return
  fi
  [[ -d "$ROOT_DIR/ui/node_modules" ]] || fail "Frontend dependencies are missing. Run npm install in ui/."
  if [[ "$(uname -s)" == "Darwin" ]]; then
    node_bin="$(command -v node)"
    launchctl remove "$FRONTEND_LABEL" >/dev/null 2>&1 || true
    launchctl submit -l "$FRONTEND_LABEL" -o "$LOG_DIR/frontend.log" -e "$LOG_DIR/frontend.log" -- \
      "$node_bin" "$ROOT_DIR/ui/node_modules/next/dist/bin/next" dev "$ROOT_DIR/ui" --hostname 0.0.0.0 --port 3000
    return
  fi
  (
    cd "$ROOT_DIR/ui"
    nohup npm run dev -- --hostname 0.0.0.0 --port 3000 </dev/null >"$LOG_DIR/frontend.log" 2>&1 &
    echo $! >"$FRONTEND_PID_FILE"
  )
}

health_all() {
  local failures=0
  wait_http "Backend API" "http://127.0.0.1:8001/health" 60 || failures=$((failures + 1))
  wait_http "Frontend" "http://127.0.0.1:3000" 60 || failures=$((failures + 1))
  wait_http "OpenSearch" "http://127.0.0.1:9200/_cluster/health" 60 || failures=$((failures + 1))
  wait_http "OpenSearch Dashboards" "http://127.0.0.1:5601/api/status" 60 || failures=$((failures + 1))
  if docker inspect -f '{{.State.Running}}' mayajal_fluent_bit 2>/dev/null | grep -qx true; then
    say "✓ Fluent Bit"
  else
    say "✗ Fluent Bit"
    failures=$((failures + 1))
  fi
  (( failures == 0 ))
}

start_all() {
  need docker; need curl; need npm
  docker info >/dev/null 2>&1 || fail "Docker is not running or is not accessible."
  say "Starting telemetry services..."
  docker compose -f "$TELEMETRY_FILE" up -d
  say "Starting backend and frontend..."
  start_backend
  start_frontend
  say "Waiting for platform health checks..."
  health_all
  say "Mayajal is ready: http://localhost:3000"
}

stop_pid_file() {
  local name="$1" pid_file="$2" pid count
  if ! pid_alive "$pid_file"; then
    rm -f "$pid_file"
    return
  fi
  pid="$(<"$pid_file")"
  say "Stopping $name (PID $pid)..."
  kill "$pid" 2>/dev/null || true
  for ((count=1; count<=10; count++)); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid" 2>/dev/null || true; fi
  rm -f "$pid_file"
}

stop_matching_listener() {
  local port="$1" expected="$2" pid command_line count
  command -v lsof >/dev/null 2>&1 || return
  while IFS= read -r pid; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$command_line" == *"$expected"* ]]; then
      say "Stopping unmanaged Mayajal listener on port $port (PID $pid)..."
      kill "$pid" 2>/dev/null || true
      for ((count=1; count<=10; count++)); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      if kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid" 2>/dev/null || true; fi
    fi
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
}

stop_all() {
  need docker
  if [[ "$(uname -s)" == "Darwin" ]]; then
    launchctl remove "$FRONTEND_LABEL" >/dev/null 2>&1 || true
    launchctl remove "$BACKEND_LABEL" >/dev/null 2>&1 || true
  fi
  stop_pid_file "frontend" "$FRONTEND_PID_FILE"
  stop_pid_file "backend" "$BACKEND_PID_FILE"
  stop_matching_listener 3000 "next"
  stop_matching_listener 8001 "uvicorn"
  say "Stopping telemetry services (data volume preserved)..."
  docker compose -f "$TELEMETRY_FILE" down
  say "Mayajal platform services are stopped."
}

end_managed_labs() {
  need docker
  local container_id project ids network_ids
  local -a projects=()
  while IFS= read -r container_id; do
    [[ -n "$container_id" ]] || continue
    project="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$container_id" 2>/dev/null || true)"
    [[ -n "$project" ]] && projects+=("$project")
  done < <(docker ps -aq --filter label=mayajal.project_id)
  if (( ${#projects[@]} == 0 )); then
    say "No Mayajal lab projects are present."
    return
  fi
  while IFS= read -r project; do
    [[ -n "$project" && "$project" != "assets" ]] || continue
    say "Ending lab project $project..."
    ids="$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
    if [[ -n "$ids" ]]; then
      # shellcheck disable=SC2086
      docker rm -f $ids >/dev/null
    fi
    network_ids="$(docker network ls -q --filter "label=com.docker.compose.project=$project")"
    if [[ -n "$network_ids" ]]; then
      # shellcheck disable=SC2086
      docker network rm $network_ids >/dev/null 2>&1 || true
    fi
  done < <(printf '%s\n' "${projects[@]}" | sort -u)
}

status_all() {
  say "Process status"
  if curl -fsS --max-time 2 http://127.0.0.1:8001/health >/dev/null 2>&1; then say "✓ Backend"; else say "✗ Backend"; fi
  if curl -fsS --max-time 2 http://127.0.0.1:3000 >/dev/null 2>&1; then say "✓ Frontend"; else say "✗ Frontend"; fi
  docker compose -f "$TELEMETRY_FILE" ps
  say "Managed lab containers: $(docker ps -q --filter label=mayajal.project_id | wc -l | tr -d ' ')"
}

usage() {
  cat <<'EOF'
Usage: ./mayajal.sh <command>

Commands:
  start      Start telemetry, backend, and frontend; wait for health checks
  health     Check every component; exit non-zero if unhealthy
  status     Show process, telemetry, and managed-lab status
  restart    Stop and restart platform services; preserve running labs
  stop       Stop frontend, backend, and telemetry; preserve labs and data
  end-all    End every Mayajal-labelled lab, then stop platform services
  logs       Follow backend, frontend, and telemetry logs
EOF
}

case "${1:-}" in
  start) start_all ;;
  health) need docker; need curl; health_all ;;
  status) need docker; need curl; status_all ;;
  restart) stop_all; start_all ;;
  stop) stop_all ;;
  end-all) end_managed_labs; stop_all ;;
  logs)
    need docker
    touch "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
    tail -n 100 -F "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log" &
    tail_pid=$!
    trap 'kill "$tail_pid" 2>/dev/null || true' EXIT INT TERM
    docker compose -f "$TELEMETRY_FILE" logs -f
    ;;
  *) usage; [[ -n "${1:-}" ]] && exit 2 || exit 0 ;;
esac
