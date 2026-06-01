#!/usr/bin/env bash
set -euo pipefail

HARMONY_PG_URL="${HARMONY_PG_URL:-postgresql://harmony:harmony@localhost:5432/harmony}"
HARMONY_ES_URL="${HARMONY_ES_URL:-http://localhost:9200}"
HARMONY_QDRANT_URL="${HARMONY_QDRANT_URL:-http://localhost:6333}"
HARMONY_BACKUP_DIR="${HARMONY_BACKUP_DIR:-./backups}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${HARMONY_BACKUP_DIR}/harmony_backup_${TIMESTAMP}"

mkdir -p "$BACKUP_PATH"

echo "==> Backup started: $TIMESTAMP"
echo "    Destination: $HARMONY_BACKUP_DIR"

# Step 1: Postgres pg_dump
echo "==> Dumping Postgres..."
pg_dump "$HARMONY_PG_URL" -Fc -f "$BACKUP_PATH/postgres.dump"
echo "    Postgres dump: $BACKUP_PATH/postgres.dump"

# Step 2: Elasticsearch snapshot
# NOTE: ES snapshot requires the backup path to be accessible by the ES node.
# In Docker, mount a shared volume at this path and set path.repo in ES config.
# See docs/BACKUP.md for setup instructions.
echo "==> Creating Elasticsearch snapshot..."
curl -s -X PUT "${HARMONY_ES_URL}/_snapshot/harmony_backup" \
  -H 'Content-Type: application/json' \
  -d "{\"type\":\"fs\",\"settings\":{\"location\":\"${BACKUP_PATH}/es_snapshot\"}}" \
  -o /dev/null
curl -s -X PUT "${HARMONY_ES_URL}/_snapshot/harmony_backup/snap_${TIMESTAMP}?wait_for_completion=true" \
  -H 'Content-Type: application/json' \
  -d '{"indices":"*","ignore_unavailable":true}' \
  -o /dev/null
echo "    ES snapshot: $BACKUP_PATH/es_snapshot"

# Step 3: Qdrant snapshot
echo "==> Creating Qdrant snapshot..."
QDRANT_SNAP_RESP=$(curl -s -X POST "${HARMONY_QDRANT_URL}/collections/harmony/snapshots")
QDRANT_SNAP_NAME=$(echo "$QDRANT_SNAP_RESP" | grep -o '"name":"[^"]*"' | head -1 | sed 's/"name":"//;s/"//')
if [ -n "$QDRANT_SNAP_NAME" ]; then
  curl -s "${HARMONY_QDRANT_URL}/collections/harmony/snapshots/${QDRANT_SNAP_NAME}" \
    -o "$BACKUP_PATH/qdrant_harmony.snapshot"
  echo "    Qdrant snapshot: $BACKUP_PATH/qdrant_harmony.snapshot"
else
  echo "    WARNING: could not retrieve Qdrant snapshot name; snapshot file may be missing"
fi

# Step 4: Archive
echo "==> Archiving..."
tar -czf "${HARMONY_BACKUP_DIR}/harmony_backup_${TIMESTAMP}.tar.gz" \
  -C "$HARMONY_BACKUP_DIR" "harmony_backup_${TIMESTAMP}"
rm -rf "$BACKUP_PATH"
echo "Backup complete: ${HARMONY_BACKUP_DIR}/harmony_backup_${TIMESTAMP}.tar.gz"
