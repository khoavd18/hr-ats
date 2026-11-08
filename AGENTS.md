# Agent Instructions

<!-- BEGIN data-analyst-skills-library: managed by skills_manager.py, do not edit inside this block -->
## Agent Skills (library-managed)

Installed from `data-analyst-skills` 1.7.1. Skill files under `.agents/skills/<name>/` and `.claude/skills/<name>/` are owned by the skills library manager. Do not edit them in place; `verify` reports any local change and `update` refuses to overwrite it.

Roles installed: `fullstack-developer`.

Precedence: project-specific rules in this file and project documentation (verified definitions, data sources, stack conventions, metrics, deployment rules) override the generic guidance in these skills. Security and privacy rules always apply. Skills use `UNKNOWN` placeholders and detect the project's stack instead of assuming one. Keep real project facts in project files (for example `docs/analytics/` or `docs/ml/`), never in the skill files.

Core rules for every skill: label claims VERIFIED, INFERRED, ASSUMED, UNKNOWN or NOT TESTED; never invent business rules, thresholds or results; never put secrets in code or logs; ask before destructive or irreversible actions.

| Skill | Use for |
|---|---|
| `backend-api-engineer` | Design, build and debug server-side APIs and services in the project's framework, such as FastAPI, Django, Flask, Express, NestJS, Spring Boot, ASP.NET Core or Go |
| `container-platform-engineer` | Build container images and run workloads on Docker Compose or Kubernetes with the project's tooling, such as Docker, Podman, Helm, Kustomize, Argo CD, Flux, EKS, AKS or GKE |
| `database-engineer` | Design and evolve application (OLTP) databases in the project's engine and tooling, such as PostgreSQL, MySQL, SQL Server, SQLite or MongoDB with Alembic, Django migrations, Prisma, Flyway, Liquibase or EF Core |
| `frontend-engineer` | Build, fix and review web and mobile user interfaces in the project's framework, such as React, Next.js, Vue, Nuxt, Angular, Svelte, React Native or Flutter |
| `infrastructure-as-code` | Write, review and safely change cloud and server infrastructure as code with the project's tool, such as Terraform, OpenTofu, Pulumi, Bicep, ARM, CloudFormation, CDK or Ansible, on AWS, Azure, GCP or on-premises |
| `kpi-metrics-engineer` | Define, specify, calculate or reconcile business KPIs and metric contracts |
| `llm-app-engineer` | Build and debug applications that call large language models through the project's SDK or framework, such as the OpenAI or Anthropic APIs, LangChain, LlamaIndex, Semantic Kernel, Ollama, vLLM or Hugging Face transformers |
| `llm-evaluation` | Evaluate generative AI and LLM outputs (chatbots, RAG answers, summaries, extraction, agents) and catch regressions when prompts, models or retrieval change |
| `ml-model-evaluation` | Evaluate, compare and report trained machine learning models for computer vision (detection, classification, segmentation) and tabular classification or regression |
| `rag-pipeline-engineer` | Build, tune and debug retrieval-augmented generation (RAG) and semantic search over the project's documents with its own stack, such as LangChain, LlamaIndex, Haystack, FAISS, pgvector, Chroma, Qdrant, Weaviate, Elasticsearch or OpenSearch |
| `secure-code-review` | Review application and infrastructure code changes for security and quality defects, defensively, in any language the project uses |
| `software-testing` | Plan, write and fix automated tests for application code in the project's framework, such as pytest, unittest, Jest, Vitest, Testing Library, Playwright, Cypress, JUnit or xUnit |
<!-- END data-analyst-skills-library -->

## Project rules: hr-ats (ưu tiên hơn hướng dẫn chung của các skill)

**Dự án:** hệ thống tuyển dụng (ATS) có AI lọc CV: kho CV tập trung, AI chấm điểm CV theo Job, email tự động từ mời phỏng vấn đến offer, theo dõi tiến độ từng recruiter, báo cáo ngày/tuần, tổng hợp Job – Ứng viên – Placement – Kết quả.
Kế hoạch đầy đủ: `docs/product/plan.md`. Paper tham khảo: `docs/research/papers.md`.

**Người dùng cuối là HR không rành công nghệ**
- Giao diện tiếng Việt, giống công cụ họ đã quen (bảng kiểu Excel, kanban kéo thả, soạn email kiểu Gmail).
- Không bắt HR viết prompt hay cấu hình AI. Kết quả AI hiển thị dạng Cao / Trung bình / Thấp kèm 2–3 lý do ngắn, có nút "Không đồng ý".
- Email từ chối và offer luôn có bước xem trước và HR bấm xác nhận trước khi gửi.
- Có hoàn tác khi đổi stage nhầm; không xoá cứng dữ liệu từ giao diện.

**AI chỉ hỗ trợ, con người quyết định**
- AI chỉ gợi ý và xếp hạng; không có luồng nào tự loại hoặc tự gửi offer mà không có người duyệt.
- Dùng workflow cố định (gọi LLM ở các bước định sẵn), không dùng multi-agent. Không dùng Airflow; việc nền chạy bằng hàng đợi Celery + Redis.
- Contract LLM, bộ đánh giá và tiêu chí chấp nhận: `docs/ml/llm-contract.md`.

**Dữ liệu cá nhân (bắt buộc, mọi skill)**
- CV là dữ liệu cá nhân, thuộc phạm vi Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP. Cần pháp chế xác nhận trước khi chạy thật.
- Che tên, ảnh, giới tính, tuổi, địa chỉ trước khi tạo embedding và trước khi gửi cho LLM chấm điểm.
- Không ghi nội dung CV, email, số điện thoại vào log, fixture test hay ví dụ trong code; dữ liệu test phải là dữ liệu giả hoặc đã ẩn danh.
- Không commit CV thật vào repo. Thư mục dữ liệu thật để ngoài repo hoặc trong `.gitignore`.
- Lưu bằng chứng đồng ý của ứng viên; có thời hạn lưu và chức năng xoá theo yêu cầu.

**Giai đoạn và stack**
- Giai đoạn hiện tại: build app theo `tasks/`; mốc M1 (T01–T18) là bản lọc CV đầu tiên HR dùng được.
- Stack đã chốt cho bản triển khai: xem `docs/specs/01-architecture.md` (Next.js, FastAPI, PostgreSQL + pgvector, Celery + Redis, Storage local/S3, Docker Compose).
- Lệnh chạy, test, lint và Definition of Done: `docs/specs/08-testing-quality.md`.

**Triển khai theo spec và task**
- Spec là nguồn sự thật: `docs/specs/` (bắt đầu từ `00-overview.md`).
- Công việc chia thành task có thứ tự trong `tasks/` (đọc `tasks/README.md` trước); mỗi lần làm một task, ghi kết quả vào `tasks/PROGRESS.md`.
- Câu hỏi phát sinh ghi vào `docs/specs/open-questions.md`, không tự đổi stack hay phạm vi.
- Giao task cho Codex: `.\scripts\run-task.ps1 -Task T01`.

**KPI báo cáo:** danh sách nháp ở `docs/metrics/kpi-list.md`; chỉ định nghĩa có `status: approved` mới là chuẩn.

## Agent commands
When the user writes one of these, follow the matching workflow file exactly:
- "Implement Txx" → tasks/_implement.md
- "Review Txx"    → tasks/_review.md
- "Fix Txx"       → tasks/_fix.md
After a task is approved and merged into `main`, set its status to `done` in tasks/PROGRESS.md.
