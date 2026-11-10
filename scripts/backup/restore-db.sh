#!/usr/bin/env bash
# restore-db.sh – khôi phục PostgreSQL từ file backup
#
# Cách dùng:
#   docker compose -f docker-compose.prod.yml exec -T db \
#     /backup/restore-db.sh /backup/hr_ats_20260101_020000.sql.gz
#
# CẢNH BÁO: script này XOÁ dữ liệu hiện tại và thay bằng bản backup.
# Dừng worker/api trước khi khôi phục:
#   docker compose -f docker-compose.prod.yml stop api worker beat

set -euo pipefail

BACKUP_FILE="${1:?Dùng: $0 <đường dẫn file backup .sql.gz>}"
DB_NAME="${POSTGRES_DB:-hr_ats}"
DB_USER="${POSTGRES_USER:-hr}"

if [[ ! -f "${BACKUP_FILE}" ]]; then
    echo "Lỗi: không tìm thấy file ${BACKUP_FILE}"
    exit 1
fi

echo "[restore] CẢNH BÁO: sẽ xoá toàn bộ dữ liệu trong ${DB_NAME} và khôi phục từ ${BACKUP_FILE}"
echo "[restore] Nhấn Ctrl+C trong 5 giây để huỷ..."
sleep 5

echo "[restore] Bắt đầu khôi phục lúc $(date)"

# Ngắt kết nối hiện có
psql -U "${DB_USER}" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" postgres

# Drop và tạo lại database
dropdb -U "${DB_USER}" --if-exists "${DB_NAME}"
createdb -U "${DB_USER}" "${DB_NAME}"

# Khôi phục
gunzip -c "${BACKUP_FILE}" | psql -U "${DB_USER}" "${DB_NAME}"

echo "[restore] Hoàn tất lúc $(date)"
echo "[restore] Khởi động lại services: docker compose -f docker-compose.prod.yml start api worker beat"
