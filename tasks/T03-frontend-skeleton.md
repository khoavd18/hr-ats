# T03 · Khung frontend
Mốc: M0 · Phụ thuộc: T01 · Spec: `01-architecture.md`, `05-ui.md` (Quy tắc chung, Bố cục)

## Mục tiêu
Next.js chạy được với bố cục, i18n tiếng Việt, API client và các trang rỗng.

## Việc cần làm
- `frontend/`: Next.js 15 App Router, TypeScript strict, Tailwind, shadcn/ui (button, input, table, dialog, drawer/sheet, toast, badge, tabs, select, dropdown), TanStack Query, ESLint + Prettier, Vitest + Testing Library, Playwright (cài, chưa có test).
- `src/i18n/vi.ts`: object chuỗi; hàm `t(key)` có kiểm tra kiểu.
- `src/lib/api.ts`: fetch wrapper tới `NEXT_PUBLIC_API_URL`, gửi cookie, gắn CSRF header, chuyển lỗi `{"error"}` thành thông báo tiếng Việt.
- Layout: thanh bên trái theo `05-ui.md`, vùng nội dung, trang placeholder cho từng mục (`/`, `/jobs`, `/candidates`, `/tasks`, `/reports`, `/settings`) với trạng thái rỗng có câu hướng dẫn.
- Component dùng chung: `AiLevelBadge` (4 mức, màu theo spec), `EmptyState`, `ConfirmDialog`, `PageHeader`.
- Scripts `dev`, `build`, `lint`, `typecheck`, `test`.

## Tiêu chí nghiệm thu
- `npm run dev` mở được các trang, điều hướng bằng thanh bên.
- `npm run lint`, `npm run typecheck`, `npm test` pass; có test cho `AiLevelBadge` và `t()`.
- Không có chuỗi hiển thị viết cứng ngoài `vi.ts`.
