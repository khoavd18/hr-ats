# 00 · Tổng quan sản phẩm

Spec này là nguồn sự thật cho agent (Codex, Claude Code) khi triển khai hr-ats. Khi spec và code mâu thuẫn, spec thắng; khi spec thiếu, xem mục "Quyết định mặc định" rồi ghi câu hỏi vào `docs/specs/open-questions.md`.

## Mục tiêu
Một web app nội bộ giúp HR:
1. Lưu và quản lý CV tập trung (kho CV có tìm kiếm).
2. Dùng AI để parse, chấm và xếp hạng CV theo từng Job.
3. Đưa ứng viên qua pipeline tuyển dụng, gửi email tự động (có xác nhận) từ mời phỏng vấn đến offer.
4. Theo dõi công việc và tiến độ của từng recruiter.
5. Báo cáo hiệu suất theo ngày/tuần, tổng hợp Job – Ứng viên – Placement – Kết quả.

## Người dùng và vai trò
| Vai trò | Mã | Quyền chính |
|---|---|---|
| Quản trị | `admin` | Mọi quyền, quản lý user, cấu hình, mẫu email, xoá dữ liệu theo yêu cầu |
| Trưởng nhóm | `lead` | Xem mọi Job và báo cáo của team, giao Job và task |
| Recruiter | `recruiter` | Chỉ thấy Job mình là owner hoặc member, và ứng viên thuộc các Job đó; thấy kho CV chung |

Người dùng là HR **không rành công nghệ**: mọi thao tác phải làm được bằng chuột, giao diện tiếng Việt, không có thuật ngữ kỹ thuật (không hiện "LLM", "embedding", "prompt", "JSON").

## Phạm vi (7 module)
1. Kho CV & ứng viên: upload hàng loạt, nhận CV từ hộp mail, parse, chống trùng, tìm kiếm.
2. Job & đơn vị tuyển: tạo Job với yêu cầu bắt buộc/ưu tiên, gắn đơn vị tuyển và recruiter.
3. Pipeline: kanban theo stage, lịch sử, hoàn tác.
4. AI lọc & đánh giá CV: chấm theo tiêu chí, xếp hạng, giải thích, phản hồi đồng ý/không đồng ý.
5. Email tự động: mẫu theo stage, xem trước, xác nhận, gửi, log.
6. Task & hoạt động recruiter: giao việc, nhắc hạn, log hoạt động tự động.
7. Báo cáo & dashboard: KPI ngày/tuần theo recruiter, Job, đơn vị tuyển; email báo cáo định kỳ.

## Nguyên tắc bắt buộc
- **AI chỉ gợi ý.** Không có luồng nào tự loại, tự đổi stage hay tự gửi email mà không có người bấm xác nhận.
- **Workflow cố định, không multi-agent.** AI được gọi ở các bước định sẵn trong `docs/specs/04-ai-pipeline.md`.
- **Dữ liệu cá nhân.** Tuân thủ `docs/specs/07-security-privacy.md` ở mọi task.
- **Không xoá cứng từ giao diện.** Xoá là soft delete; xoá vĩnh viễn chỉ qua quy trình yêu cầu xoá dữ liệu của admin.
- **Mọi thứ chạy được không cần API key thật**: có `FakeLLM` và `FakeEmbedder` cho dev/test.

## Quyết định mặc định (đổi được bằng cấu hình)
| Câu hỏi chưa chốt | Mặc định trong code | Cách đổi |
|---|---|---|
| HR nội bộ hay headhunt nhiều client | Bảng `hiring_units` với `kind = client | department`; nhãn trên UI lấy từ `HIRING_UNIT_LABEL` (mặc định "Đơn vị tuyển") | Biến môi trường |
| Nhà cung cấp LLM | Adapter `fake | anthropic | openai | ollama`; dev/test dùng `fake` | `LLM_PROVIDER`, `LLM_MODEL` |
| Model embedding | `BAAI/bge-m3` chạy local (1024 chiều); test dùng `fake` | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |
| Gửi email | SMTP; dev dùng Mailpit | `SMTP_*`; adapter Gmail/Microsoft Graph để sau |
| Nhận CV từ hộp mail | IMAP | `IMAP_*` |
| Đăng nhập | Email + mật khẩu; SSO để sau | — |
| Ngôn ngữ / múi giờ | Tiếng Việt / `Asia/Ho_Chi_Minh` | — |

## Ngoài phạm vi
Cổng cho client/ứng viên, app mobile, tự đăng tin lên job board, tính lương/hoa hồng, chấm điểm phỏng vấn bằng video/giọng nói, multi-tenant.

## Thuật ngữ
| Từ | Nghĩa trong code |
|---|---|
| Job | Một vị trí tuyển (`jobs`) |
| Đơn vị tuyển | Client hoặc phòng ban cần tuyển (`hiring_units`) |
| Ứng viên | Một người (`candidates`), có thể có nhiều file CV |
| Hồ sơ ứng tuyển | Một ứng viên cho một Job (`applications`), là trục của pipeline và báo cáo |
| Stage | Bước trong pipeline, xem `02-data-model.md` |
| Placement | Ứng viên nhận việc (`placements`) |

## Bản đồ spec
- `01-architecture.md`: stack, cấu trúc repo, dịch vụ, cấu hình
- `02-data-model.md`: bảng, enum, ràng buộc
- `03-api.md`: endpoint
- `04-ai-pipeline.md`: trích text, parse, ẩn danh, chấm điểm, embedding, đánh giá
- `05-ui.md`: màn hình và quy tắc UX
- `06-email-reports.md`: email, task, báo cáo, KPI
- `07-security-privacy.md`: phân quyền, dữ liệu cá nhân
- `08-testing-quality.md`: lệnh chạy, test, Definition of Done
- `open-questions.md`: câu hỏi agent gặp khi làm
