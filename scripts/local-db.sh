#!/usr/bin/env bash
# Dedicated local test cluster only. Does not touch a system PostgreSQL service.
set -euo pipefail
pilot_root="$(cd "$(dirname "$0")/.." && pwd)"
pilot_dir="$pilot_root/.local"
pilot_pg_bin="${PG_BIN:-/opt/homebrew/opt/postgresql@18/bin}"
pilot_db_port="${PILOT_DB_PORT:-55439}"
pilot_http_port="${PILOT_PORT:-18081}"
for pilot_port in "$pilot_db_port" "$pilot_http_port"; do
  if ! [[ "$pilot_port" =~ ^[0-9]+$ ]] || ((pilot_port < 1024 || pilot_port > 65535)); then
    echo "Use ports in 1024..65535." >&2
    exit 2
  fi
done
if [[ ! -x "$pilot_pg_bin/pg_ctl" ]]; then
  echo "Set PG_BIN to the PostgreSQL bin directory." >&2
  exit 2
fi

case "${1:-}" in
  start)
    mkdir -p "$pilot_dir/pg-socket"
    if [[ ! -f "$pilot_dir/pgdata/PG_VERSION" ]]; then
      "$pilot_pg_bin/initdb" -D "$pilot_dir/pgdata" -U pilot --auth=trust --encoding=UTF8 --locale=C
    fi
    if ! "$pilot_pg_bin/pg_ctl" -D "$pilot_dir/pgdata" status >/dev/null 2>&1; then
      "$pilot_pg_bin/pg_ctl" -D "$pilot_dir/pgdata" -l "$pilot_dir/postgres.log" \
        -o "-h 127.0.0.1 -p $pilot_db_port -k '$pilot_dir/pg-socket' -c log_min_error_statement=panic" -w start
    fi
    if [[ "$(sed -n '4p' "$pilot_dir/pgdata/postmaster.pid")" != "$pilot_db_port" ]]; then
      echo "The project's DB is already running on a different port; stop it before changing ports." >&2
      exit 2
    fi
    pilot_psql=("$pilot_pg_bin/psql" -X -h 127.0.0.1 -p "$pilot_db_port" -U pilot -v ON_ERROR_STOP=1)
    if [[ "$("${pilot_psql[@]}" -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='daynomy_feedback_test'")" != 1 ]]; then
      "$pilot_pg_bin/createdb" -h 127.0.0.1 -p "$pilot_db_port" -U pilot daynomy_feedback_test
    fi
    if [[ "$("${pilot_psql[@]}" -d daynomy_feedback_test -Atc "SELECT to_regclass('public.feedbacks') IS NOT NULL")" != t ]]; then
      "${pilot_psql[@]}" -d daynomy_feedback_test -f "$pilot_root/app/migrations/001_feedbacks.sql"
    fi
    umask 077
    {
      printf 'export CARGO_HOME=%q\n' "$pilot_dir/cargo"
      printf 'export DATABASE_URL=%q\n' "postgresql://pilot@127.0.0.1:$pilot_db_port/daynomy_feedback_test"
      printf 'export PILOT_TEST_DB_URL=%q\n' "postgresql://pilot@127.0.0.1:$pilot_db_port/daynomy_feedback_test"
      printf 'export PORT=%q\n' "$pilot_http_port"
      printf 'export PILOT_BASE_URL=%q\n' "http://127.0.0.1:$pilot_http_port"
    } > "$pilot_dir/pilot.env"
    echo "Local test DB ready. Run: source .local/pilot.env"
    ;;
  stop)
    "$pilot_pg_bin/pg_ctl" -D "$pilot_dir/pgdata" -m fast -w stop
    ;;
  *)
    echo "Usage: bash scripts/local-db.sh {start|stop}" >&2
    exit 2
    ;;
esac
