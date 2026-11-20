import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { ConsentDialog } from "@/components/consent-dialog";
import { PrivacySettings } from "@/components/privacy-settings";
import { api, ApiError } from "@/lib/api";
import { t } from "@/i18n/vi";

const state = vi.hoisted(() => ({ role: "admin" }));
vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({ user: { id: "admin", role: state.role } }),
}));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));

const candidate = {
  id: "candidate",
  full_name: "Ứng viên giả T29",
  consent_at: null,
  retention_until: "2026-11-30",
  expired_at: null,
  purge_pending_at: null,
  purged_at: null,
};
const request = {
  id: "request",
  candidate_id: "candidate",
  candidate_name: candidate.full_name,
  requested_by_note: "Bằng chứng giả",
  kind: "delete",
  status: "open",
  created_at: "2026-11-10T01:00:00Z",
};

function show(node = <PrivacySettings />) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { cache, ...render(<QueryClientProvider client={cache}>{node}</QueryClientProvider>) };
}

beforeEach(() => {
  state.role = "admin";
  vi.mocked(api)
    .mockReset()
    .mockImplementation(async (path) => {
      if (path.startsWith("/settings/retention")) return { items: [candidate], total: 21 } as never;
      if (path.startsWith("/data-requests")) return { items: [request], total: 1 } as never;
      if (path.startsWith("/users"))
        return { items: [{ id: "admin", full_name: "Quản trị giả" }], total: 1 } as never;
      return {
        items: [
          {
            id: "audit",
            actor_id: null,
            action: "candidate.purge",
            entity: "candidate",
            entity_id: "candidate",
            occurred_at: "2026-11-10T01:00:00Z",
          },
        ],
        total: 1,
      } as never;
    });
});

it.each(["lead", "recruiter"])("hides data management and does not fetch for %s", (role) => {
  state.role = role;
  expect(show().container).toBeEmptyDOMElement();
  expect(api).not.toHaveBeenCalled();
});

it("filters upcoming/expired/all candidates, searches and paginates without exposing old results", async () => {
  show();
  expect(await screen.findByText(candidate.full_name)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: t("privacy.next") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(expect.stringContaining("page=2"), expect.anything()),
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: t("privacy.state") }),
    "expired",
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/settings/retention?state=expired&q=&page=1",
      expect.anything(),
    ),
  );
  await userEvent.type(screen.getByLabelText(t("privacy.search")), "giả");
  await userEvent.click(screen.getByRole("button", { name: t("privacy.searchButton") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/settings/retention?state=expired&q=gi%E1%BA%A3&page=1",
      expect.anything(),
    ),
  );
});

it("requires explicit evidence and converts Vietnam wall time when recording consent", async () => {
  const saved = vi.fn().mockResolvedValue(undefined);
  show(<ConsentDialog candidateId="candidate" onSaved={saved} />);
  await userEvent.click(screen.getByRole("button", { name: t("privacy.recordConsent") }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("button", { name: t("common.confirm") })).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText(t("privacy.consentAt")), {
    target: { value: "2026-11-09T15:30" },
  });
  await userEvent.type(within(dialog).getByLabelText(t("privacy.evidence")), "Bằng chứng giả");
  await userEvent.click(within(dialog).getByRole("button", { name: t("common.confirm") }));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  expect(api).toHaveBeenCalledWith("/candidates/candidate/consent", {
    method: "POST",
    body: JSON.stringify({
      consent_at: "2026-11-09T15:30:00+07:00",
      note: "Bằng chứng giả",
      extend_retention: false,
    }),
  });
});

it("keeps extension evidence after an API error and sends the explicit renewal flag", async () => {
  vi.mocked(api).mockRejectedValueOnce(
    new ApiError(409, "CONSENT_NOT_NEW", t("privacy.consentNotNew")),
  );
  show(<ConsentDialog candidateId="candidate" extend onSaved={async () => {}} />);
  await userEvent.click(screen.getByRole("button", { name: t("privacy.extend") }));
  fireEvent.change(screen.getByLabelText(t("privacy.consentAt")), {
    target: { value: "2026-11-09T15:30" },
  });
  await userEvent.type(screen.getByLabelText(t("privacy.evidence")), "Bằng chứng giả");
  await userEvent.click(screen.getByRole("button", { name: t("common.confirm") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("privacy.consentNotNew"));
  expect(screen.getByLabelText(t("privacy.evidence"))).toHaveValue("Bằng chứng giả");
  expect(JSON.parse(vi.mocked(api).mock.calls[0][1]?.body as string).extend_retention).toBe(true);
});

it("creates a request then requires a separate destructive confirmation", async () => {
  show();
  await userEvent.click(await screen.findByRole("button", { name: t("privacy.createRequest") }));
  const dialog = screen.getByRole("dialog");
  await userEvent.type(
    within(dialog).getByLabelText(t("privacy.requestEvidence")),
    "Bằng chứng giả",
  );
  await userEvent.click(within(dialog).getByRole("button", { name: t("privacy.createRequest") }));
  await userEvent.click(await screen.findByRole("button", { name: t("privacy.execute") }));
  expect(screen.getByRole("dialog")).toHaveTextContent(candidate.full_name);
  expect(api).not.toHaveBeenCalledWith("/data-requests/request/execute", expect.anything());
  await userEvent.click(screen.getByRole("button", { name: t("common.cancel") }));
  expect(api).not.toHaveBeenCalledWith("/data-requests/request/execute", expect.anything());
  await userEvent.click(screen.getByRole("button", { name: t("privacy.execute") }));
  await userEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: t("privacy.execute") }),
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/data-requests/request/execute", { method: "POST" }),
  );
});

it("shows the system actor and passes actor/action filters to the audit API", async () => {
  show();
  await userEvent.click(screen.getByRole("tab", { name: t("privacy.audit") }));
  expect(await screen.findByText(t("privacy.action.purge"), { selector: "td" })).toBeVisible();
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: t("privacy.actor") }),
    "system",
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: t("privacy.action") }),
    "candidate.purge",
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/audit-log?page=1&action=candidate.purge&system=true",
      expect.anything(),
    ),
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: t("privacy.actor") }),
    "admin",
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/audit-log?page=1&action=candidate.purge&actor_id=admin",
      expect.anything(),
    ),
  );
});

it("handles failed, empty and pending-purge candidate lists", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("synthetic offline"));
  show();
  await userEvent.click(await screen.findByRole("button", { name: t("common.retry") }));
  expect(await screen.findByText(candidate.full_name)).toBeVisible();
  vi.mocked(api).mockResolvedValueOnce({ items: [], total: 0 });
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: t("privacy.state") }),
    "expired",
  );
  expect(await screen.findByText(t("privacy.empty"))).toBeVisible();
  vi.mocked(api).mockResolvedValueOnce({
    items: [{ ...candidate, purge_pending_at: "2026-11-10T01:00:00Z" }],
    total: 1,
  });
  await userEvent.selectOptions(screen.getByRole("combobox", { name: t("privacy.state") }), "all");
  expect(await screen.findByText(t("privacy.frozen"))).toBeVisible();
  expect(screen.queryByRole("button", { name: t("privacy.extend") })).not.toBeInTheDocument();
});
