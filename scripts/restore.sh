#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${1:?Usage: restore.sh <archive.tar.gz>}"

HARMONY_PG_URL="${HARMONY_PG_URL:-postgresql://harmony:harmony@localhost:5432/harmony}"
HARMONY_QDRANT_URL="${HARMONY_QDRANT_URL:-http://localhost:6333}"

RESTORE_DIR=$(mktemp -d)
trap "rm -rf '$RESTORE_DIR'" EXIT

echo "==> Extracting archive: $ARCHIVE"
tar -xzf "$ARCHIVE" -C "$RESTORE_DIR"

BACKUP_DIR=$(ls "$RESTORE_DIR")
BACKUP_PATH="$RESTORE_DIR/$BACKUP_DIR"

# Step 1: Postgres restore
echo "==> Restoring Postgres from $BACKUP_PATH/postgres.dump"
pg_restore --clean --if-exists -d "$HARMONY_PG_URL" "$BACKUP_PATH/postgres.dump"
echo "    Postgres restore complete"

# Step 2: Elasticsearch restore
# ES restore requires registering the snapshot repository on the target cluster.
# This is too cluster-specific for automated restore. See docs/BACKUP.md for the
# manual procedure.
echo "==> Elasticsearch restore: manual step required"
echo "    ES snapshot location: $BACKUP_PATH/es_snapshot"
echo "    See docs/BACKUP.md for ES snapshot restore procedure"

# Step 3: Qdrant restore
echo "==> Restoring Qdrant from $BACKUP_PATH/qdrant_harmony.snapshot"
if [ -f "$BACKUP_PATH/qdrant_harmony.snapshot" ]; then
  curl -s -X POST "${HARMONY_QDRANT_URL}/collections/harmony/snapshots/upload" \
    --data-binary "@$BACKUP_PATH/qdrant_harmony.snapshot" \
    -H "Content-Type: application/octet-stream"
  echo "    Qdrant restore complete"
else
  echo "    WARNING: $BACKUP_PATH/qdrant_harmony.snapshot not found; skipping Qdrant restore"
fi

echo "Restore complete"
