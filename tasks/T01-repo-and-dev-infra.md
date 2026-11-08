# T01 · Khung repo và hạ tầng dev
Mốc: M0 · Phụ thuộc: — · Spec: `01-architecture.md`, `07-security-privacy.md` (mục Dữ liệu trong repo)

## Mục tiêu
Repo có cấu trúc thư mục chuẩn và một lệnh khởi động hạ tầng dev.

## Việc cần làm
- Tạo các thư mục theo `01-architecture.md` (`backend/`, `frontend/`, `prompts/`, `eval/`, `data/sample_cvs/`, `scripts/`, `var/` có `.gitkeep`).
- `docker-compose.yml` với `db` (pgvector/pgvector:pg16, user/pass/db `hr`/`hr`/`hr_ats`, volume), `redis`, `mailpit`, `minio` (profile `s3`). Script init tạo extension `vector`, `unaccent`, và DB `hr_ats_test`.
- `.env.example` đúng như spec; `.gitignore` bổ sung: `.env`, `var/`, `node_modules/`, `.venv/`, `__pycache__/`, `eval/reports/*.json`, `*.local.*`.
- `README.md`: thêm mục "Chạy dev" với các lệnh từ `08-testing-quality.md` (chỉ những lệnh đã tồn tại sau task này; các lệnh khác ghi "có sau T02/T03").
- `.editorconfig` (UTF-8, LF, 2 dấu cách cho TS/JSON/YAML, 4 cho Python).

## Tiêu chí nghiệm thu
- `docker compose up -d db redis mailpit` chạy được; `psql` vào `hr_ats` thấy extension `vector` và `unaccent`; DB `hr_ats_test` tồn tại.
- Mailpit web mở được ở cổng 8025.
- Không có file `.env` hay dữ liệu thật trong repo.

## Ngoài phạm vi
Code backend/frontend.
