#!/usr/bin/env bash
# Finds every Docker volume that contains a PostgreSQL data directory and shows
# how many chat events / users each one holds.
#
# Safety: a volume attached to a RUNNING container is never opened (two Postgres
# servers on one data directory can corrupt it). Only detached volumes are
# probed with a temporary container that is removed right after.
#
# Usage: bash scripts/find_postgres_volumes.sh
set -euo pipefail

PG_IMAGE="postgres:15"
DB_USER="${POSTGRES_USER:-bot}"
DB_NAME="${POSTGRES_DB:-bot}"

echo "Current compose volume: $(docker compose config --format json 2>/dev/null | grep -o '"academicquestionbot_postgres_data[^"]*"' | head -1 || echo academicquestionbot_postgres_data)"
echo

for volume in $(docker volume ls -q); do
  # Cheap check: does the volume look like a Postgres data dir?
  if ! docker run --rm -v "$volume":/data:ro alpine:3 test -f /data/PG_VERSION 2>/dev/null; then
    continue
  fi
  version=$(docker run --rm -v "$volume":/data:ro alpine:3 cat /data/PG_VERSION 2>/dev/null)
  used_by=$(docker ps -a --filter volume="$volume" --format '{{.Names}}' | paste -sd, -)
  running=$(docker ps --filter volume="$volume" --format '{{.Names}}' | paste -sd, -)
  created=$(docker volume inspect -f '{{.CreatedAt}}' "$volume")

  if [[ -n "$running" ]]; then
    echo "volume:   $volume"
    echo "  created: $created   postgres: $version   IN USE by running: $running (not probed)"
    echo
    continue
  fi

  # Postgres cannot run on a read-only mount; the volume is detached, so a
  # short-lived server is safe. It is stopped (and removed) right after the query.
  name="pgprobe_$RANDOM"
  docker run -d --rm --name "$name" -v "$volume":/var/lib/postgresql/data \
    -e POSTGRES_PASSWORD=probe "postgres:${version}" >/dev/null 2>&1 || { echo "$volume: cannot start postgres:$version"; continue; }
  for _ in $(seq 1 30); do docker exec "$name" pg_isready -U "$DB_USER" >/dev/null 2>&1 && break; sleep 1; done
  counts=$(docker exec "$name" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT (SELECT COUNT(*) FROM chat_analytics)||' chat events, '||(SELECT COUNT(*) FROM telegram_users)||' users, last: '||COALESCE((SELECT MAX(created_at)::text FROM chat_analytics),'-')" 2>/dev/null || echo "no bot tables")
  docker stop "$name" >/dev/null 2>&1 || true

  echo "volume:   $volume"
  echo "  created: $created   postgres: $version   used by: ${used_by:-<none>}"
  echo "  data:    $counts"
  echo
done
