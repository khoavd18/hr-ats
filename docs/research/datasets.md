# Bộ dữ liệu CV công khai (chỉ để phát triển và đánh giá)

Tải về `var/datasets/` (đã gitignore), không commit, không đưa vào bản demo công khai.

| Bộ | Nguồn | Nội dung | Dùng cho |
|---|---|---|---|
| Resume Dataset | Kaggle `snehaanbhawal/resume-dataset` | ~2.484 CV tiếng Anh, có PDF, 24 nhóm nghề (scrape từ livecareer.com) | Test trích text, parse PDF |
| UpdatedResumeDataSet | Kaggle `gauravduttakiit/resume-dataset` | 962 CV, text, nghiêng IT | Thử nhanh |
| resume-job-description-fit | Hugging Face `cnamuangtoun/resume-job-description-fit` | ~8k cặp CV–JD, nhãn No/Potential/Good Fit; bộ khó, nhãn nhiễu | Đánh giá chấm điểm tương đối |
| CareerCorpus | Mendeley Data `wzzwn37gmd` | 302 CV ẩn danh, 6 nhóm nghề, điểm của 2 chuyên gia | Đo đồng thuận AI – người chấm |
| ResumeAtlas | Hugging Face `ahmedheakl/resume-atlas` | 13.389 CV, 43 nhóm nghề; giấy phép CC BY-NC-ND (phi thương mại) | Kiểm tra quy mô |
| Viet-Resume-VQA | Hugging Face `5CD-AI/Viet-Resume-VQA` (phải đồng ý điều khoản) | Ảnh CV tiếng Việt | Test OCR CV ảnh tiếng Việt |
| VietJobs | GitHub `VinNLP/VietJobs` | 48.092 tin tuyển dụng tiếng Việt | JD mẫu tiếng Việt cho đánh giá |
| CV giả tiếng Việt | `eval/generate_synthetic_cvs.py` | Sinh trong repo, có nhãn | Test end-to-end, seed, demo |
