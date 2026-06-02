# Backup and Restore

Covers disaster recovery for the three stateful stores: Postgres, Elasticsearch, and Qdrant. Crawl output on disk is optionally backed up when `HARMONY_CRAWL_DATA_DIR` is set (see Configuration below).

## Requirements

- `pg_dump` / `pg_restore` — ships with PostgreSQL client tools
- `curl` — for ES and Qdrant REST APIs
- `tar` — for archiving
- Elasticsearch filesystem snapshot repository configured (see [ES snapshot requirements](#es-snapshot-requirements))

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HARMONY_PG_URL` | `postgresql://harmony:harmony@localhost:5432/harmony` | Postgres connection string |
| `HARMONY_ES_URL` | `http://localhost:9200` | Elasticsearch base URL |
| `HARMONY_QDRANT_URL` | `http://localhost:6333` | Qdrant base URL |
| `HARMONY_BACKUP_DIR` | `./backups` | Directory where archives are written |
| `HARMONY_CRAWL_DATA_DIR` | _(unset)_ | Path to crawl output directory. When set, crawl output is archived into the backup. Omit to skip. |

Do not hardcode credentials in cron entries. Use an env file or secret manager and source it before running the scripts.

## Running a Backup

```bash
HARMONY_BACKUP_DIR=/mnt/backups ./scripts/backup.sh
```

The script creates a timestamped archive at `$HARMONY_BACKUP_DIR/harmony_backup_YYYYMMDD_HHMMSS.tar.gz`. Each archive contains:

- `postgres.dump` — pg_dump custom-format dump
- `es_snapshot/` — Elasticsearch filesystem snapshot
- `qdrant_harmony.snapshot` — Qdrant collection snapshot
- `crawl_output/` — crawl output directory (only present when `HARMONY_CRAWL_DATA_DIR` is set)

## Scheduling with Cron

Daily backup at 2 AM:

```
0 2 * * * cd /path/to/harmony && HARMONY_BACKUP_DIR=/mnt/backups ./scripts/backup.sh >> /var/log/harmony-backup.log 2>&1
```

Source an env file if credentials are not in the process environment:

```
0 2 * * * cd /path/to/harmony && set -a && . /etc/harmony/backup.env && set +a && ./scripts/backup.sh >> /var/log/harmony-backup.log 2>&1
```

## Storage Destination Options

**Local disk** — Set `HARMONY_BACKUP_DIR` to any writable path. Ensure enough disk space.

**NFS mount** — Mount the NFS share and point `HARMONY_BACKUP_DIR` at it.

**S3 / GCS via rclone**:

```bash
# After backup completes, sync to remote
rclone copy /mnt/backups s3:my-bucket/harmony-backups/
```

Or wrap the backup script:

```bash
./scripts/backup.sh && rclone sync /mnt/backups s3:my-bucket/harmony-backups/
```

Refer to [rclone docs](https://rclone.org/) for configuration.

## ES Snapshot Requirements

Elasticsearch snapshots use the `fs` (filesystem) repository type. The path used by `backup.sh` must be accessible by the ES node.

**Docker setup** — Add a shared volume mount to the ES service in `docker-compose.yml`:

```yaml
elasticsearch:
  environment:
    - path.repo=/snapshots
  volumes:
    - es_snapshots:/snapshots
```

Mount the same volume on the host or in the backup container so `backup.sh` can write to it.

**Alternative** — Use the [S3 repository plugin](https://www.elastic.co/guide/en/elasticsearch/reference/current/repository-s3.html) for cloud-hosted ES. In that case, replace the `fs` snapshot registration in `backup.sh` with an S3 repository config and skip the local snapshot path entirely.

## Restore Procedure

```bash
./scripts/restore.sh /mnt/backups/harmony_backup_20260601_020000.tar.gz
```

The script:

1. Extracts the archive to a temp directory
2. Runs `pg_restore --clean --if-exists` against `$HARMONY_PG_URL`
3. Prints the ES snapshot path and instructs you to follow the manual ES restore (below)
4. POSTs the Qdrant snapshot to `$HARMONY_QDRANT_URL/collections/harmony/snapshots/upload`

### Manual ES Restore

The ES restore requires registering the snapshot repository on the target cluster and then restoring from the snapshot. The exact steps depend on your target cluster configuration.

1. Register the snapshot repository pointing to the extracted `es_snapshot/` directory:

```bash
curl -X PUT "$HARMONY_ES_URL/_snapshot/harmony_backup" \
  -H 'Content-Type: application/json' \
  -d '{"type":"fs","settings":{"location":"/path/to/extracted/es_snapshot"}}'
```

2. List available snapshots:

```bash
curl "$HARMONY_ES_URL/_snapshot/harmony_backup/_all"
```

3. Restore:

```bash
curl -X POST "$HARMONY_ES_URL/_snapshot/harmony_backup/<snapshot_name>/_restore?wait_for_completion=true" \
  -H 'Content-Type: application/json' \
  -d '{"indices":"*","ignore_unavailable":true}'
```

See the [Elasticsearch snapshot and restore docs](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html) for details.

## Recovery Time Estimates

| Store | Typical RTO |
|-------|-------------|
| Postgres | Minutes (depends on DB size) |
| Qdrant | Minutes to hours (depends on collection size and disk speed) |
| Elasticsearch | Varies — see [ES restore docs](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshots-restore-snapshot.html) |

## Security Notes

- Archives contain a Postgres dump. API keys stored in the DB are Fernet-encrypted at rest, but the dump still contains all encrypted data. Store backup archives encrypted at rest.
- Do not hardcode `HARMONY_PG_URL` (or any credentials) directly in cron tab entries. Use an env file readable only by the backup user, or a secret manager.
- Restrict access to `$HARMONY_BACKUP_DIR` so only the backup process and authorized admins can read archives.

---

For data portability between Harmony instances (not disaster recovery), use the admin UI export/import feature.
