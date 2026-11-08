import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { CvBank } from "@/components/cv-bank";
import { AddFromBank } from "@/components/bank-add-dialog";
import { api, ApiError } from "@/lib/api";
import type { BankCandidate } from "@/lib/cv-bank-types";
import { t } from "@/i18n/vi";

vi.mock("@/components/auth-provider", () => ({ useAuth: () => ({ user: { role } }) }));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
let role = "admin";
let rows: BankCandidate[];
function show(component = <CvBank />) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{component}</QueryClientProvider>);
}
beforeEach(() => {
  role = "admin";
  rows = ["A", "B"].map((id) => ({
    id,
    full_name: `Ứng viên giả ${id}`,
    current_title: "Kế toán",
    years_experience: "3.50",
    skills: ["Excel"],
    location: "Địa điểm giả",
    source: "upload",
    created_at: "2026-11-08T01:00:00Z",
    possible_duplicate: null,
  }));
  rows[0].possible_duplicate = { ...rows[1] };
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.startsWith("/candidates?") || path.startsWith("/candidates/search/semantic?"))
      return { items: structuredClone(rows), total: rows.length };
    if (path.startsWith("/jobs/job/suggestions"))
      return { items: structuredClone(rows), total: rows.length };
    if (path.startsWith("/jobs?")) return { items: [{ id: "job", title: "Vị trí giả" }], total: 1 };
    if (path === "/applications") return { ai_status: "pending" };
    if (path.endsWith("/merge")) {
      rows = [rows[1]];
      return rows[0];
    }
    throw new Error("Unexpected mocked API path");
  });
});

it("renders Vietnamese cards, sends all filters, and selects semantic search explicitly", async () => {
  show();
  await screen.findByRole("article", { name: rows[0].full_name });
  expect(screen.getByText(t("bank.duplicate"))).toBeVisible();
  await userEvent.type(screen.getByLabelText(t("bank.search")), "ke toan");
  await userEvent.type(screen.getByLabelText(t("bank.filter.skills")), "excel");
  await userEvent.type(screen.getByLabelText(t("bank.filter.min_years")), "2");
  await userEvent.type(screen.getByLabelText(t("bank.filter.location")), "da nang");
  await userEvent.selectOptions(screen.getByLabelText(t("bank.source")), "upload");
  await userEvent.click(screen.getByRole("button", { name: t("bank.find") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/candidates?page=1&page_size=20&q=ke+toan&skills=excel&min_years=2&location=da+nang&source=upload",
      expect.anything(),
    ),
  );
  await userEvent.click(screen.getByLabelText(t("bank.semantic")));
  await userEvent.click(screen.getByRole("button", { name: t("bank.find") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining("/candidates/search/semantic?"),
      expect.anything(),
    ),
  );
});

it("compares both candidates, cancels safely, switches the kept record and confirms a merge", async () => {
  show();
  const trigger = await screen.findByRole("button", { name: t("bank.merge") });
  await userEvent.click(trigger);
  const dialog = screen.getByRole("dialog", { name: t("bank.mergeTitle") });
  expect(within(dialog).getAllByRole("article")).toHaveLength(2);
  expect(within(dialog).getByText(t("bank.mergeWarning"))).toBeVisible();
  expect(within(dialog).getByRole("button", { name: t("common.cancel") })).toHaveFocus();
  await userEvent.keyboard("{Escape}");
  expect(trigger).toHaveFocus();
  expect(vi.mocked(api).mock.calls.some(([path]) => path.endsWith("/merge"))).toBe(false);
  await userEvent.click(trigger);
  await userEvent.click(screen.getByLabelText(t("bank.keepThis") + rows[0].full_name));
  await userEvent.click(screen.getByRole("button", { name: t("bank.confirmMerge") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/candidates/B/merge", {
      method: "POST",
      body: JSON.stringify({ into_id: "A" }),
    }),
  );
});

it("keeps the merge comparison open on failure for retry", async () => {
  const original = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.endsWith("/merge"))
      throw new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable"));
    return original(path, options);
  });
  show();
  await userEvent.click(await screen.findByRole("button", { name: t("bank.merge") }));
  await userEvent.click(screen.getByRole("button", { name: t("bank.confirmMerge") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  expect(screen.getByRole("dialog")).toBeVisible();
  expect(screen.getByRole("button", { name: t("bank.confirmMerge") })).toBeEnabled();
});

it("allows recruiters to search summaries and directs merges to a lead", async () => {
  role = "recruiter";
  show();
  expect(await screen.findByText(t("bank.askMerge"))).toBeVisible();
  expect(screen.queryByRole("button", { name: t("bank.merge") })).not.toBeInTheDocument();
});

it("chooses a permitted Job from the bank and adds the selected candidate", async () => {
  show();
  await userEvent.click(await screen.findByLabelText(t("bank.select") + rows[0].full_name));
  await userEvent.click(screen.getByRole("button", { name: t("bank.addToJob") }));
  await screen.findByRole("option", { name: "Vị trí giả" });
  await userEvent.selectOptions(screen.getByLabelText(t("bank.chooseJob")), "job");
  await userEvent.click(screen.getByRole("button", { name: t("bank.addSelected") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/applications", {
      method: "POST",
      body: JSON.stringify({ candidate_id: "A", job_id: "job" }),
    }),
  );
  expect(
    await screen.findByText(rows[0].full_name + t("common.separator") + t("bank.added")),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: t("bank.addSelected") })).toBeDisabled();
});

it("adds multiple suggestions, isolates failures and retries only the failed candidate", async () => {
  const original = vi.mocked(api).getMockImplementation()!;
  let failB = true;
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/applications") {
      const body = JSON.parse(options?.body as string);
      if (body.candidate_id === "A")
        throw new ApiError(409, "APPLICATION_EXISTS", t("bank.alreadyAdded"));
      if (failB) {
        failB = false;
        throw new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable"));
      }
      return { ai_status: "failed" };
    }
    return original(path, options);
  });
  show(<AddFromBank jobId="job" />);
  await userEvent.click(screen.getByRole("button", { name: t("bank.fromBank") }));
  await userEvent.click(await screen.findByLabelText(t("bank.select") + rows[0].full_name));
  await userEvent.click(screen.getByLabelText(t("bank.select") + rows[1].full_name));
  await userEvent.click(screen.getByRole("button", { name: t("bank.addSelected") }));
  expect(
    await screen.findByText(rows[0].full_name + t("common.separator") + t("bank.alreadyAdded")),
  ).toBeVisible();
  await waitFor(() =>
    expect(screen.getByRole("button", { name: t("bank.addSelected") })).toBeEnabled(),
  );
  expect(screen.getByLabelText(t("bank.select") + rows[0].full_name)).not.toBeChecked();
  expect(screen.getByLabelText(t("bank.select") + rows[1].full_name)).toBeChecked();
  await userEvent.click(screen.getByRole("button", { name: t("bank.addSelected") }));
  expect(
    await screen.findByText(rows[1].full_name + t("common.separator") + t("bank.addedScoreFailed")),
  ).toBeVisible();
  const calls = vi
    .mocked(api)
    .mock.calls.filter(([path]) => path === "/applications")
    .map(([, options]) => JSON.parse(options?.body as string).candidate_id);
  expect(calls).toEqual(["A", "B", "B"]);
});

it("shows actionable empty and error states without rendering server payloads", async () => {
  rows = [];
  show();
  expect(await screen.findByText(t("bank.empty"))).toBeVisible();
});

it("retries a failed bank request", async () => {
  vi.mocked(api).mockRejectedValueOnce(
    new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable")),
  );
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  await userEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  expect(await screen.findByRole("article", { name: rows[0].full_name })).toBeVisible();
});
