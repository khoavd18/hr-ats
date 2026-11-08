# 08 · Kiểm thử và Definition of Done

## Lệnh chuẩn (agent dùng đúng các lệnh này)
| Việc | Lệnh |
|---|---|
| Hạ tầng dev | `docker compose up -d db redis mailpit` |
| Cài backend | `cd backend && uv sync` |
| Migration | `cd backend && uv run alembic upgrade head` |
| Chạy API | `cd backend && uv run uvicorn app.main:app --reload` |
| Chạy worker | `cd backend && uv run celery -A app.workers.celery_app worker -Q ai,email,default -l info` (Windows thêm `-P solo`) |
| Test backend | `cd backend && uv run pytest` |
| Lint backend | `cd backend && uv run ruff check . && uv run ruff format --check .` |
| Typecheck backend | `cd backend && uv run mypy app` |
| Seed dev | `cd backend && uv run python -m app.scripts.seed` |
| Cài frontend | `cd frontend && npm ci` |
| Chạy frontend | `cd frontend && npm run dev` |
| Test frontend | `cd frontend && npm test` |
| Lint frontend | `cd frontend && npm run lint && npm run typecheck` |
| E2E | `cd frontend && npx playwright test` (cần API + web + seed) |
| Đánh giá AI | `cd backend && uv run python ../eval/run_score_eval.py --provider fake` |

Test backend chạy trên DB Postgres riêng (`hr_ats_test`, tạo bởi fixture), Celery chạy ở chế độ eager, `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake`, email gửi vào bộ nhớ. **Test không được gọi mạng ra ngoài.**

Nền T02: fixture chỉ cho phép DB trên localhost và luôn chọn `hr_ats_test`, dùng transaction ngoài + savepoint để rollback cả khi code gọi `session.commit()`. Test migration từ DB trống dùng DB tạm có tên `hr_ats_test_t02_<uuid>` trên cùng server, chỉ xoá đúng DB do fixture vừa tạo. DB dev và `hr_ats_test` được giữ lại. Migration đầu chỉ bật extension `vector`/`unaccent`; downgrade giữ extension vì chúng có thể do hạ tầng T01 tạo trước Alembic.

## Definition of Done cho mỗi task
1. Đáp ứng toàn bộ tiêu chí nghiệm thu trong file task.
2. Có test cho logic mới (unit cho services/ai, API test cho endpoint); test cũ vẫn pass.
3. Lint và typecheck sạch.
4. Có migration Alembic nếu đổi schema; `alembic upgrade head` chạy được trên DB trống.
5. Không có PII thật trong code, test, log, fixture.
6. Chuỗi giao diện mới nằm trong `vi.ts`.
7. Nếu thay đổi hợp đồng (API, schema, KPI) thì cập nhật spec tương ứng trong cùng commit.
8. Cuối task, ghi tóm tắt vào `tasks/PROGRESS.md`: task id, việc đã làm, file chính, lệnh test đã chạy và kết quả, việc còn lại / câu hỏi.
