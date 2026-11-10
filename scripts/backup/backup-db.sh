#!/usr/bin/env bash
# backup-db.sh – backup PostgreSQL và giữ 14 bản gần nhất
#
# Cách dùng (chạy trong container db hoặc từ máy host):
#   docker compose -f docker-compose.prod.yml exec db /backup/backup-db.sh
#
# Hoặc đặt cronjob trên máy host (chạy lúc 2:00 SA hằng ngày):
#   0 2 * * * docker compose -f /srv/hr-ats/docker-compose.prod.yml exec -T db /backup/backup-db.sh

set -euo pipefail

BACKUP_DIR="/backup"
DB_NAME="${POSTGRES_DB:-hr_ats}"
DB_USER="${POSTGRES_USER:-hr}"
KEEP_DAYS=14

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "[backup] Bắt đầu backup ${DB_NAME} lúc $(date)"

# Dump và nén
pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_FILE}"

echo "[backup] Đã tạo: ${BACKUP_FILE} ($(du -sh "${BACKUP_FILE}" | cut -f1))"

# Xoá các bản cũ hơn KEEP_DAYS ngày
find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
REMAINING=$(find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" | wc -l)
echo "[backup] Giữ ${REMAINING} bản backup (tối đa ${KEEP_DAYS} ngày)"
echo "[backup] Hoàn tất lúc $(date)"
