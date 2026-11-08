# hr-ats: kế hoạch dự án

Bản kế hoạch chi tiết (phân hệ, quy trình, kiến trúc, dữ liệu, AI, KPI, lộ trình, rủi ro) nằm ở doc:
https://claude.ai/artifact/UJNKZaDWnt9PVVP4LiXVxT

## Quyết định đã chốt
- Tên project: hr-ats.
- Người dùng: HR không rành công nghệ.
- Build app trực tiếp theo spec `docs/specs/` và task `tasks/` (giao cho Codex); mốc M1 là bản lọc CV dùng được.
- Không dùng multi-agent, không dùng Airflow.

## Câu hỏi còn mở
- HR nội bộ một công ty hay công ty headhunt nhiều client? (quyết định có cần phần Client/Placement hay không)
- Số recruiter và số CV mỗi tháng.
- Nguồn CV hiện tại (email, TopCV, VietnamWorks, LinkedIn, giới thiệu).
- Google Workspace hay Microsoft 365.
- Có được gửi CV qua API LLM nước ngoài không.

## Tài liệu tham khảo
- Paper liên quan và cách áp dụng: `docs/research/papers.md`.

## Spec và task triển khai
- Spec kỹ thuật: `docs/specs/` · Task cho agent: `tasks/` · Bộ dữ liệu: `docs/research/datasets.md`.
