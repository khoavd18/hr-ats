# T31 · Bộ đánh giá AI
Mốc: M5 · Phụ thuộc: T12 · Spec: `04` (Đánh giá), `docs/ml/llm-contract.md`, `docs/research/datasets.md`

## Việc cần làm
- `scripts/download_datasets.py`: tải các bộ trong `datasets.md` vào `var/datasets/` (Kaggle qua API token người dùng tự cấu hình; Hugging Face qua `datasets`); bộ cần đồng ý điều khoản thì in hướng dẫn thay vì tải.
- `eval/run_parse_eval.py`, `eval/run_score_eval.py`, `eval/run_bias_check.py` theo spec; tham số `--provider`, `--model`, `--prompt-version`, `--data synthetic|careercorpus|jdfit|dir:<path>`.
- Báo cáo Markdown vào `eval/reports/` với bảng chỉ số và 10 ví dụ sai tiêu biểu (dùng text đã ẩn danh).
- Cập nhật `docs/ml/llm-contract.md` mục Bộ đánh giá với lệnh chạy cụ thể.

## Tiêu chí nghiệm thu
- Chạy được toàn bộ với `--provider fake --data synthetic` trong test (không mạng).
- Bias check báo cáo chênh lệch điểm theo nhóm tên trên bộ CV giả.
