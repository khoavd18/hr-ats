# CV giả cho test, seed và demo

VERIFIED: bộ dữ liệu T06 được sinh offline từ danh sách giả trong
`generate_synthetic_cvs.py`. Không có hồ sơ, liên hệ, công ty hay lịch sử làm việc
được lấy từ người thật. Tên trường và công ty có chữ **Mô phỏng / Giả lập**.
Tên người là tổ hợp mẫu tiếng Việt; các nhóm vùng miền chỉ dùng để bảo đảm độ phủ
fixture, không suy luận xuất xứ của người thật.

Seed dev, pytest và các lệnh đánh giá tự chuẩn bị bộ CV giả khi cần. Để sinh
thủ công, chạy từ `src/backend/` sau khi cài dependency đã khóa:

```sh
uv sync
uv run python -m hr_ats_ai.eval.generate_synthetic_cvs
```

Mặc định đầu ra là `src/ai/var/sample_cvs/` và được Git bỏ qua. Đường dẫn truyền
qua `--out` tính từ thư mục hiện tại. `--count` nhận 1–10000; mỗi sáu CV luân phiên một
bộ bố cục, nên từ 30 CV có ít nhất năm CV mỗi kiểu. Bộ 60 CV có 35 PDF, 25 DOCX,
10 CV mỗi kiểu: một cột, hai cột, bảng, ảnh đại diện giả bằng khối màu, tiếng Anh,
scan có xoay nhẹ và nhiễu. Sáu nhóm nghề gồm backend, frontend, kế toán, kinh doanh,
marketing và nhân sự; có nam/nữ và ba nhóm tên miền Bắc/Trung/Nam.

Có thể chạy lại vào thư mục chứa đúng bộ giả có cùng số lượng/định dạng. Khi đổi
số lượng hoặc thư mục có file khác, dùng thư mục đầu ra mới. Script từ chối ghi đè
bộ không đầy đủ hoặc tài liệu khác và không tự xoá file cũ.

## Khả năng tái lập

VERIFIED: cùng seed và dependency trong `src/backend/uv.lock` cho cùng byte ở mọi file,
gồm JSON, DOCX và PDF scan. Random dùng instance có seed; ngày tham chiếu cố định
`2026-01-01`; metadata PDF, timestamp và thứ tự entry ZIP của DOCX đều cố định.
Font PDF là Noto Sans Regular được commit tại `assets/`, dùng giấy phép OFL 1.1
kèm theo trong `assets/OFL.txt`. [Font gốc](https://github.com/notofonts/noto-fonts/blob/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf)
và [giấy phép gốc](https://github.com/notofonts/noto-fonts/blob/main/LICENSE).
SHA-256 font: `b85c38ecea8a7cfb39c24e395a4007474fa5a4fc864f6ee33309eb4948d232d5`.
Không cần tải font, gọi LLM, embedding hoặc mạng khi sinh/test.

Test đối chiếu SHA-256 của cả 121 file sinh lại với bộ mẫu gốc qua
`hr_ats_ai/eval/assets/sample_cvs.sha256`. Windows và Linux dùng cùng `uv.lock`.

NOT TESTED: so byte giữa các bản nâng dependency hoặc mọi nền tảng khác nhau.
Sau khi nâng thư viện render/compression, chạy lại test tái lập trước khi thay fixture.
DOCX dùng tên font Arial để trình đọc hiển thị, không nhúng font độc quyền; hình thức
DOCX tùy trình đọc. PDF nhúng toàn bộ Noto Sans nên không cần font hệ điều hành.
Không subset font vì tag subset của MuPDF khác giữa bản build Windows/Linux;
khối ảnh đại diện DOCX dùng BMP để tránh khác biệt nén PNG giữa các bản Pillow.

## Nhãn version 1

Schema Pydantic trong `schemas.py` là contract dùng cho bộ dữ liệu giả, tách khỏi
schema parse production ở T09. Các model từ chối trường thừa.

| File/model | Nội dung |
|---|---|
| `<id>.json` / `CVLabel` | `schema_version=1`, `synthetic=true`, `id`, `file_name`, `layout`, `language`, `career`, `region`, `gender`, `full_name`, `email`, `phone`, `date_of_birth`, `location`, `current_title`, `years_experience`, `skills`, `experience`, `education`, `expected_level` |
| `experience[]` | `company`, `title`, `start`, `end`, `description`; tháng dạng `YYYY-MM` |
| `education[]` | `school`, `degree`, `major`, `start`, `end` |
| `jobs.json` / `JobDataset` | `schema_version=1`, `synthetic=true`, `seed`, `reference_date`, năm `jobs`, ma trận `expected_level[cv_id][job_id]` |
| `jobs[]` | `id`, `title`, `description`, `must_have`, `nice_to_have` |

Mọi email dạng `<id>@example.com`; SĐT hiển thị `09xx 000 xxx` và có đúng mười chữ
số sau khi bỏ khoảng trắng. Không dùng các liên hệ này để gửi email/gọi điện.
Mỗi CV có đúng năm nhãn `high | medium | low | insufficient` tương ứng năm Job;
bản trong file CV và ma trận trong `jobs.json` phải giống nhau.

ASSUMED: nhãn phù hợp là kịch bản fixture có chủ đích, chưa phải đánh giá của HR.
Năm Job thuộc backend, frontend, kế toán, kinh doanh và marketing; CV nhân sự làm
ví dụ khác nghề. Mỗi Job có hai kỹ năng bắt buộc, ít nhất ba năm kinh nghiệm liên
quan và hai kỹ năng ưu tiên. Cùng nghề: một năm/một kỹ năng là `low`; hai năm/đủ
hai kỹ năng bắt buộc/chưa có kỹ năng ưu tiên là `medium`; sáu năm/đủ kỹ năng là
`high`. Khác nghề là `low`. Ở ví dụ hai năm, tiêu chí ba năm được hiểu là `partial`,
hai kỹ năng là `met`, hai ưu tiên là `not_met`: theo công thức spec 04 được 62 điểm
và mức `medium`. Đây là mặc định nhãn giả, không thêm quy tắc đánh giá production.
CV đều có đủ nội dung nên chưa sinh kịch bản `insufficient`.

## Kiểm tra

Tại `src/backend/`:

```sh
uv run pytest tests/unit/test_synthetic_cvs.py -q
uv run ruff check ../ai
uv run ruff format --check ../ai
```

Test validate tất cả nhãn và ma trận Job, cặp file CV/JSON, dữ liệu liên hệ giả,
nguồn công ty, tổng số tháng kinh nghiệm, đủ bố cục/nghề/nhóm tên, dung lượng dưới
30 MB và SHA-256 của toàn bộ bộ dữ liệu sau khi sinh lại. Test đọc lại nội dung
PDF/DOCX để đối chiếu với nhãn, kiểm tra bảng/cột/ảnh đại diện và scan không có
text layer nhưng có nét chữ. Kiểm tra scan chưa thay thế đánh giá OCR của T08.
CLI chỉ ghi tổng số CV và seed; lỗi schema được thay bằng thông báo chung, có test
hồi quy bảo đảm không phản chiếu trường liên hệ của nhãn bị hỏng.
