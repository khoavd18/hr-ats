# T09 · LLM adapter và prompt
Mốc: M1 · Phụ thuộc: T02 · Spec: `04-ai-pipeline.md` (LLM adapter, bước 3, bước 8)

## Việc cần làm
- `app/ai/llm.py`: Protocol `LLMClient.complete_json(...)`; `FakeLLM`, `AnthropicLLM`, `OpenAILLM`, `OllamaLLM`; factory theo `LLM_PROVIDER`; timeout, retry, log metadata không có nội dung; validate bằng Pydantic, gọi lại một lần kèm lỗi validate.
- `app/ai/prompts.py`: nạp `prompts/<task>/v<N>.md` (frontmatter: `version`, `task`, `description`; thân có phần `## system` và `## user` với biến Jinja2).
- Viết prompt `prompts/parse_cv/v1.md` (3 phần basic/experience/skills — có thể là 3 file `parse_cv_basic`, `parse_cv_experience`, `parse_cv_skills`) và `prompts/score_cv/v1.md`. Prompt viết bằng tiếng Việt, yêu cầu trả `null` khi không có thông tin, không suy đoán giới tính/tuổi, chỉ trả JSON.
- `app/ai/schemas.py`: Pydantic schema cho output parse và score.
- `FakeLLM`: với parse, trích tên/kỹ năng bằng heuristic đơn giản từ text; với score, đánh `met` nếu từ khoá của tiêu chí xuất hiện trong text, `not_met` nếu không — đủ để test end-to-end tất định.

## Tiêu chí nghiệm thu
- Test: factory chọn đúng adapter; FakeLLM trả output hợp lệ theo schema; output sai schema → retry rồi lỗi; log không chứa text đầu vào.
- Có một script `uv run python -m app.scripts.llm_smoke --provider anthropic` để người dùng tự thử với key thật (không chạy trong test).
