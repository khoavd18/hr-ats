import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { EmailCompose } from "@/components/email-compose";
import { ProfileEmail } from "@/components/profile-email";
import { api, ApiError } from "@/lib/api";
import type { EmailDraft } from "@/lib/email-types";
import { t } from "@/i18n/vi";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
const draft: EmailDraft = {
  application_id: "app",
  template_id: "invite",
  to_email: "synthetic@example.invalid",
  subject: "Mời phỏng vấn giả",
  body: "Lịch phỏng vấn giả <script>private</script>",
  body_html: "<p>Lịch phỏng vấn giả</p>",
  has_calendar: true,
};
function show(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(<QueryClientProvider client={client}>{node}</QueryClientProvider>) };
}
beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/email-messages") return { id: "message" };
    return {};
  });
});

it("does not save or send on preview, skip or Escape", async () => {
  const close = vi.fn();
  const view = show(<EmailCompose draft={draft} onClose={close} />);
  expect(screen.getByLabelText(t("email.to"))).toHaveValue(draft.to_email);
  expect(screen.getByLabelText(t("email.body"))).toHaveValue(draft.body);
  expect(screen.getByText(t("email.calendar"))).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
  expect(api).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: t("email.skip") }));
  expect(close).toHaveBeenCalledOnce();
  view.unmount();
  show(<EmailCompose draft={draft} onClose={close} />);
  await userEvent.keyboard("{Escape}");
  expect(close).toHaveBeenCalledTimes(2);
  expect(api).not.toHaveBeenCalled();
});

it("sends edited values only after Gửi and blocks duplicate submit and closing", async () => {
  let resolve!: (value: unknown) => void;
  vi.mocked(api).mockImplementation((path) =>
    path === "/email-messages"
      ? new Promise((done) => {
          resolve = done;
        })
      : Promise.resolve({}),
  );
  const close = vi.fn();
  show(<EmailCompose draft={draft} onClose={close} />);
  fireEvent.change(screen.getByLabelText(t("email.subject")), { target: { value: "HR sửa" } });
  fireEvent.change(screen.getByLabelText(t("email.body")), {
    target: { value: "Nội dung HR sửa" },
  });
  const send = screen.getByRole("button", { name: t("email.send") });
  fireEvent.click(send);
  fireEvent.click(send);
  expect(api).toHaveBeenCalledOnce();
  const data = JSON.parse(vi.mocked(api).mock.calls[0][1]!.body as string);
  expect(data).toEqual({
    application_id: "app",
    template_id: "invite",
    to_email: draft.to_email,
    subject: "HR sửa",
    body: "Nội dung HR sửa",
  });
  await userEvent.keyboard("{Escape}");
  expect(close).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: t("email.skip") })).toBeDisabled();
  expect(screen.getByLabelText(t("email.body"))).toBeDisabled();
  await act(async () => resolve({ id: "message" }));
  expect(api).toHaveBeenLastCalledWith("/email-messages/message/send", { method: "POST" });
  expect(close).toHaveBeenCalledOnce();
});

it("keeps the saved draft after send errors, retries without creating another, and cancels it", async () => {
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/email-messages") return { id: "message" };
    if (path.endsWith("/send"))
      throw new ApiError(503, "EMAIL_QUEUE_UNAVAILABLE", t("email.queueUnavailable"));
    return {};
  });
  const close = vi.fn();
  show(<EmailCompose draft={draft} onClose={close} />);
  await userEvent.click(screen.getByRole("button", { name: t("email.send") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("email.queueUnavailable"));
  expect(screen.getByLabelText(t("email.body"))).toHaveValue(draft.body);
  await userEvent.click(screen.getByRole("button", { name: t("email.send") }));
  expect(vi.mocked(api).mock.calls.filter(([path]) => path === "/email-messages")).toHaveLength(1);
  expect(close).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: t("email.skip") }));
  expect(api).toHaveBeenLastCalledWith("/email-messages/message/cancel", { method: "POST" });
  expect(close).toHaveBeenCalledOnce();
});

it("ignores a late create response after unmount and leaves an inert draft", async () => {
  let resolve!: (value: unknown) => void;
  vi.mocked(api).mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const close = vi.fn();
  const success = vi.spyOn(toast, "success");
  const view = show(<EmailCompose draft={draft} onClose={close} />);
  fireEvent.click(screen.getByRole("button", { name: t("email.send") }));
  view.unmount();
  await act(async () => resolve({ id: "message" }));
  expect(api).toHaveBeenCalledOnce();
  expect(close).not.toHaveBeenCalled();
  expect(success).not.toHaveBeenCalled();
});

it("shows email history, missing email, safe preview and retries only on a click", async () => {
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.includes("/templates?")) return { items: [{ id: "invite", name: "Mẫu giả" }] };
    if (path.includes("?application_id="))
      return {
        total: 1,
        items: [
          {
            id: "failed",
            status: "failed",
            subject: "Thư giả bị lỗi",
            to_email: draft.to_email,
            body_html: "<p>Thư giả</p>",
            scheduled_for: null,
            sent_at: null,
            created_at: "2026-11-09T00:00:00Z",
          },
        ],
      };
    if (path.endsWith("/preview")) return draft;
    return {};
  });
  show(<ProfileEmail applicationId="app" email={null} />);
  expect(api).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: t("email.title") }));
  expect(screen.getByText(t("email.noAddress"))).toBeVisible();
  await userEvent.click(await screen.findByText("Thư giả bị lỗi"));
  const preview = screen.getByTitle(t("pipeline.emailPreview"));
  expect(preview).toHaveAttribute("sandbox", "");
  expect(preview.getAttribute("srcdoc")).toContain("default-src 'none'");
  expect(vi.mocked(api).mock.calls.every(([, options]) => options?.method !== "POST")).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: t("email.retry") }));
  expect(api).toHaveBeenCalledWith("/email-messages/failed/send", { method: "POST" });
  await userEvent.selectOptions(screen.getByLabelText(t("email.template")), "invite");
  await userEvent.click(screen.getByRole("button", { name: t("email.useTemplate") }));
  expect(await screen.findByRole("dialog")).toBeVisible();
  expect(screen.getByLabelText(t("email.body"))).toHaveValue(draft.body);
  expect(vi.mocked(api).mock.calls.filter(([path]) => path === "/email-messages")).toHaveLength(0);
});

it("shows load errors with retry and allows free composition in an empty history", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("SYNTHETIC_PRIVATE"));
  vi.mocked(api).mockImplementation(async (path) =>
    path.includes("templates?") ? { items: [] } : { items: [], total: 0 },
  );
  show(<ProfileEmail applicationId="app" email={draft.to_email} />);
  await userEvent.click(screen.getByRole("button", { name: t("email.title") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unknown"));
  await userEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: t("email.compose") }));
  expect(screen.getByLabelText(t("email.to"))).toHaveValue(draft.to_email);
  expect(screen.getByRole("button", { name: t("email.send") })).toBeDisabled();
});
