# Paper tham khảo cho hr-ats

Tổng hợp ngày 2026-11-05. Mỗi paper ghi: nội dung chính, và áp dụng vào phần nào của dự án.

## 1. Parse CV

| Paper | Nội dung chính | Áp dụng |
|---|---|---|
| [Layout-Aware Parsing Meets Efficient LLMs](https://arxiv.org/abs/2510.09722) (Zhu et al., 2025) | Ghép metadata PDF với OCR, dựng lại thứ tự đọc cho CV nhiều cột; tách trích xuất thành nhiều prompt song song; model 0.6B fine-tune đạt độ chính xác gần model lớn. Có code và dataset. | Bước trích text + parse; hướng giảm chi phí về sau |
| [Study of Information Extraction in Resume](https://eprints.uet.vnu.edu.vn/eprints/id/eprint/3349/) (ĐH Công nghệ – ĐHQG HN, 2018) | NER trên CV tiếng Việt, F1 trên 81%. | Hiểu lỗi đặc thù tiếng Việt khi parse |

## 2. Khớp CV với JD

| Paper | Nội dung chính | Áp dụng |
|---|---|---|
| [ConFit](https://arxiv.org/abs/2401.16349) | Embedding CV và JD bằng contrastive learning, xếp hạng hàng nghìn CV trong mili giây. | Lọc thô bằng vector |
| [ConFit v2](https://arxiv.org/abs/2502.12361) | Thêm hard-negative mining để phân biệt cặp khớp và gần khớp. | Fine-tune embedding khi có dữ liệu |
| [PJFCANN](https://arxiv.org/abs/2206.09116) | Dùng lịch sử tuyển thành công làm tín hiệu, không chỉ độ giống nội dung. | Tận dụng phản hồi đồng ý/không đồng ý của recruiter |
| [APJFNN](https://arxiv.org/abs/1812.08947) | Person-job fit theo từng năng lực, có khả năng giải thích. | Rubric chấm theo từng tiêu chí |

## 3. LLM chấm điểm và độ tin cậy

| Paper | Nội dung chính | Áp dụng |
|---|---|---|
| [Application of LLM Agents in Recruitment](https://arxiv.org/abs/2401.08315) (Lo et al., 2024) | Framework agent tóm tắt và chấm CV, nhanh hơn thủ công 11 lần trong mô phỏng. | Tham khảo kiến trúc (lưu ý: chỉ là mô phỏng) |
| [Measuring Validity in LLM-based Resume Screening](https://arxiv.org/abs/2602.18550) (Castleman et al., 2026) | Nhiều model chọn ứng viên giỏi hơn không ổn định, không đứng ngoài khi hai người ngang nhau, chọn khác nhau theo nhóm nhân khẩu học. Có framework kiểm định và code. | Thiết kế bộ đánh giá trong `docs/ml/llm-contract.md` |
| [Signal or Noise?](https://arxiv.org/abs/2507.08019) (Varshney & Ganuthula, 2025) | LLM nhất quán hơn khi prompt chi tiết nhưng khác biệt đáng kể so với chuyên gia nhân sự. | Lý do giữ con người duyệt cuối |

## 4. Thiên lệch

| Paper | Nội dung chính | Áp dụng |
|---|---|---|
| [Gender, Race, and Intersectional Bias in Resume Screening via Language Model Retrieval](https://arxiv.org/abs/2407.20371) (Wilson & Caliskan, 2024) | Chính các model embedding cũng thiên lệch theo tên ứng viên. | Che thông tin định danh trước cả bước embedding |
| [FAIRE](https://arxiv.org/abs/2504.01420) (2025) | Hai cách kiểm tra thiên lệch: chấm trực tiếp và xếp hạng nhóm 5 CV. Có code. | Bộ test thiên lệch |
| [Can LLMs Hire Fairly?](https://www.alphaxiv.org/abs/2606.28978) (Gao, Jiang, Yan, 2026) | 14 model; chiều thiên lệch thay đổi qua các thế hệ model. | Kiểm tra lại mỗi khi đổi model |

## 5. Dữ liệu tiếng Việt

| Paper | Nội dung chính | Áp dụng |
|---|---|---|
| [VietJobs](https://arxiv.org/abs/2603.05262) (LREC 2026) | 48.092 tin tuyển dụng tiếng Việt, 16 nhóm nghề; [GitHub](https://github.com/VinNLP/VietJobs). | Thử embedding tiếng Việt cho JD, phân loại ngành nghề |

## Rút ra cho dự án
1. Che thông tin định danh trước cả embedding lẫn LLM.
2. Tách prompt parse thành nhiều prompt nhỏ chạy song song.
3. Dùng framework của Castleman et al. hoặc FAIRE để kiểm tra AI trước khi bật cho cả team; kiểm tra lại mỗi khi đổi model hoặc prompt.
4. Về lâu dài: fine-tune model nhỏ để parse và embedding kiểu ConFit trên dữ liệu tuyển dụng thật.
