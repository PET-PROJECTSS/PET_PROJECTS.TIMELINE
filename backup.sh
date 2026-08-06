#!/bin/sh
# Снимает дамп PostgreSQL и кладёт в ./backups/backup-<дата>.sql.gz
#
# Использование:
#   ./backup.sh            — из корня проекта (где лежит docker-compose.yml)
#   ./backup.sh /path/to/timeline
#
# Cron (ежедневно в 03:00):
#   0 3 * * * /opt/projects/timeline/backup.sh /opt/projects/timeline >> /var/log/timeline-backup.log 2>&1
set -eu

COMPOSE_DIR="${1:-$(pwd)}"
cd "$COMPOSE_DIR"

POSTGRES_USER="${POSTGRES_USER:-timeline}"
POSTGRES_DB="${POSTGRES_DB:-timeline}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION="${BACKUP_RETENTION:-14}"

mkdir -p "$BACKUP_DIR"
stamp=$(date +%F_%H%M%S)
out="$BACKUP_DIR/backup-$stamp.sql.gz"

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$out"

# Удаляем дампы старше RETENTION дней
find "$BACKUP_DIR" -name 'backup-*.sql.gz' -mtime "+$RETENTION" -delete 2>/dev/null || true

echo "Backup: $out"
