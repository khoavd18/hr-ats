import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { MailboxSettings } from "@/components/mailbox-settings";
import { api } from "@/lib/api";
import { t } from "@/i18n/vi";

const state = vi.hoisted(() => ({ role: "lead" }));
vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({ user: { role: state.role } }),
}));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MailboxSettings />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  state.role = "lead";
  vi.mocked(api)
    .mockReset()
    .mockResolvedValue({ enabled: false, last_read_at: null, last_error: null });
});

it("shows disabled and never-read state without credential fields", async () => {
  show();
  expect(await screen.findByText(t("mailbox.disabled"))).toBeVisible();
  expect(screen.getByText(t("mailbox.never"))).toBeVisible();
  expect(screen.getByText(t("mailbox.noError"))).toBeVisible();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(api).toHaveBeenCalledWith(
    "/settings/mailbox",
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  );
});

it("shows enabled, local time and a Vietnamese connection error", async () => {
  vi.mocked(api).mockResolvedValue({
    enabled: true,
    last_read_at: "2026-11-09T01:30:00Z",
    last_error: "IMAP_READ_FAILED",
  });
  show();
  expect(await screen.findByText(t("mailbox.enabled"))).toBeVisible();
  expect(screen.getByText(/08:30/)).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent(t("mailbox.IMAP_READ_FAILED"));
});

it("retries a load error", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("offline"));
  show();
  await userEvent.click(await screen.findByRole("button", { name: t("common.retry") }));
  expect(await screen.findByText(t("mailbox.disabled"))).toBeVisible();
  expect(api).toHaveBeenCalledTimes(2);
});

it("does not fetch or render for recruiters", () => {
  state.role = "recruiter";
  const view = show();
  expect(view.container).toBeEmptyDOMElement();
  expect(api).not.toHaveBeenCalled();
});
