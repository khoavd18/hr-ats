# Hướng dẫn triển khai hr-ats

## Yêu cầu máy chủ

| Mục | Tối thiểu | Khuyến nghị |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Ổ đĩa | 40 GB SSD | 100 GB SSD |
| OS | Ubuntu 22.04 / 24.04 LTS | Ubuntu 24.04 LTS |
| Docker | ≥ 25 | Docker Engine 27 |
| Docker Compose | ≥ 2.24 | Docker Compose 2.29 |

**Lưu ý:**
- Model embedding `BAAI/bge-m3` cần thêm ~2 GB RAM và ~1.5 GB ổ đĩa (tải lần đầu).
- Nếu dùng Tesseract OCR với nhiều CV scan cùng lúc, cần thêm CPU.

---

## Cài đặt lần đầu

### 1. Cài Docker

```bash
# Ubuntu
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Đăng xuất và đăng nhập lại để áp dụng group
```

### 2. Clone repo

```bash
git clone https://github.com/<org>/hr-ats.git /srv/hr-ats
cd /srv/hr-ats
```

### 3. Cấu hình môi trường

```bash
cp .env.prod.example .env.prod
# Mở .env.prod và điền các giá trị bắt buộc:
#   SECRET_KEY, POSTGRES_PASSWORD, ANTHROPIC_API_KEY (hoặc OPENAI_API_KEY),
#   SMTP_HOST, SMTP_USER, SMTP_PASSWORD, DOMAIN
nano .env.prod
```

**Biến bắt buộc phải đặt trước khi chạy:**

| Biến | Mô tả |
|---|---|
| `SECRET_KEY` | Key bí mật JWT (tạo bằng `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `POSTGRES_PASSWORD` | Mật khẩu PostgreSQL (đặt mạnh, ít nhất 16 ký tự) |
| `DOMAIN` | Domain của hệ thống (ví dụ: `ats.example.com`) |
| `LLM_PROVIDER` + API key | `anthropic` + `ANTHROPIC_API_KEY` hoặc `openai` + `OPENAI_API_KEY` |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | Cấu hình SMTP để gửi email |
| `FRONTEND_ORIGIN` | URL đầy đủ của frontend (ví dụ: `https://ats.example.com`) |

### 4. Build image

```bash
cd /srv/hr-ats
docker compose --env-file .env.prod -f docker-compose.prod.yml build
```

### 5. Khởi động database trước

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d db redis
# Chờ db healthy (khoảng 10-20 giây)
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

### 6. Chạy migration

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm api \
    alembic upgrade head
```

### 7. Tạo tài khoản admin đầu tiên

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm api \
    python -m app.scripts.create_admin --email admin@example.com
```

Lệnh hỏi mật khẩu hai lần qua terminal và tạo user với role `admin`.

### 8. Khởi động toàn bộ hệ thống

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
# Kiểm tra tất cả services đang chạy
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

### 9. Kiểm tra hoạt động

```bash
# API health
curl -f https://ats.example.com/health

# Logs
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api
```

---

## Backup database hằng ngày

### Cài đặt tự động (cron trên máy host)

```bash
# Mở crontab
crontab -e

# Thêm dòng sau (backup lúc 2:00 SA hằng ngày)
0 2 * * * docker compose --env-file /srv/hr-ats/.env.prod -f /srv/hr-ats/docker-compose.prod.yml exec -T db /backup/backup-db.sh >> /srv/hr-ats/src/backend/var/backups/backup.log 2>&1
```

### Chạy backup thủ công

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db /backup/backup-db.sh
```

### Kiểm tra các bản backup

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db ls -lh /backups/
```

Backup lưu tại `src/backend/var/backups/` trên máy chủ và xuất hiện trong container tại `/backups/`. Script dọn file cũ hơn thời hạn 14 ngày. Ví dụ sao lưu ra ngoài:

```bash
# Copy bản backup mới nhất ra máy host
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db sh -c \
    "ls -t /backups/hr_ats_*.sql.gz | head -1 | xargs cat" \
    > /mnt/backup/hr_ats_$(date +%Y%m%d).sql.gz
```

---

## Khôi phục database

> **Cảnh báo:** Khôi phục sẽ xoá toàn bộ dữ liệu hiện tại.

```bash
# 1. Dừng api và worker (tránh ghi dữ liệu khi đang restore)
docker compose --env-file .env.prod -f docker-compose.prod.yml stop api worker beat

# 2. Xem danh sách backup
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db ls -lh /backups/

# 3. Khôi phục từ file backup cụ thể
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
    /backup/restore-db.sh /backups/hr_ats_20260101_020000.sql.gz

# 4. Khởi động lại
docker compose --env-file .env.prod -f docker-compose.prod.yml start api worker beat
```

---

## Cập nhật phiên bản

Khi chuyển từ bố cục cũ, giữ lại các volume PostgreSQL và storage với cùng tên dự án Compose. Nếu cấu hình đã dùng đường dẫn tuyệt đối `/app/var/storage`, cập nhật nó thành `/app/src/backend/var/storage`. Chuyển các bản backup cần giữ từ `scripts/backup/` cũ vào `src/backend/var/backups/` và cập nhật lệnh cron theo phần trên.

```bash
cd /srv/hr-ats

# 1. Lấy code mới
git pull origin main

# 2. Build image mới
docker compose --env-file .env.prod -f docker-compose.prod.yml build

# 3. Chạy migration (nếu có thay đổi schema)
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm api \
    alembic upgrade head

# 4. Khởi động lại services (rolling update)
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --no-deps api worker beat web

# 5. Kiểm tra
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=50 api
```

---

## Mã hoá ổ đĩa

Khuyến nghị bật LUKS cho partition chứa dữ liệu trước khi cài đặt:

```bash
# Ví dụ mã hoá partition /dev/sdb (thực hiện trên máy chủ trước khi mount)
cryptsetup luksFormat /dev/sdb
cryptsetup open /dev/sdb sdb_crypt
mkfs.ext4 /dev/mapper/sdb_crypt
mount /dev/mapper/sdb_crypt /srv

# Thêm vào /etc/crypttab và /etc/fstab để tự mount khi khởi động
```

Với môi trường cloud, dùng encrypted volume của nhà cung cấp:
- AWS: EBS với KMS encryption
- GCP: Persistent Disk với CMEK
- Azure: Azure Disk Encryption

---

## Giám sát và log

```bash
# Xem log real-time
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f

# Xem log theo service
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f worker

# Dung lượng volumes
docker system df -v
```

---

## Khắc phục sự cố thường gặp

| Vấn đề | Kiểm tra | Giải pháp |
|---|---|---|
| API không khởi động | `logs api` | Kiểm tra `DATABASE_URL`, `SECRET_KEY` trong `.env.prod` |
| Worker không nhận job | `logs worker` | Kiểm tra `REDIS_URL`; thử restart worker |
| Email không gửi được | `logs api` tìm `SMTP` | Kiểm tra SMTP credentials và port |
| Tesseract lỗi | `logs worker` tìm `OCR` | Đảm bảo image đã cài `tesseract-ocr-vie` |
| Caddy không cấp TLS | `logs caddy` | Kiểm tra DNS đã trỏ đúng domain; port 80/443 mở |
| Hết dung lượng | `df -h` | Dọn Docker: `docker system prune`; xoá backup cũ |
