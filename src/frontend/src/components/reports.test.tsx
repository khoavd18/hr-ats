import { cloneElement, type ReactElement, type ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { Reports } from "@/components/reports";
import { api, ApiError } from "@/lib/api";
import { stages } from "@/lib/ranking-types";
import {
  activityTypes,
  presetDates,
  reportNumber,
  reportParams,
  reportRate,
  validPeriod,
  type Metrics,
  type ReportFilters,
} from "@/lib/report-types";
import { t } from "@/i18n/vi";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
const auth = vi.hoisted(() => ({
  user: { id: "mine", role: "recruiter" } as { id: string; role: string } | null,
}));
vi.mock("@/components/auth-provider", () => ({ useAuth: () => auth }));
// Only layout measurement is replaced: real Recharts renderers still run in jsdom.
vi.mock("recharts", async (original) => ({
  ...(await original<typeof import("recharts")>()),
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>
      {cloneElement(children as ReactElement<{ width: number; height: number }>, {
        width: 500,
        height: 288,
      })}
    </div>
  ),
}));

const metric = (count: number, rate: number | null = 0.8): Metrics => ({
  new_cvs: count,
  screened: 2,
  submitted: 1,
  interviews: { total: 3, elapsed: 1, upcoming: 2 },
  offers: 1,
  placements: 1,
  overdue_jobs: 0,
  funnel: stages.map((stage, index) => ({
    stage,
    count: index === 0 ? 1 : 2,
    next_stage: index < 5 ? stages[index + 1] : null,
    next_count: index < 5 ? 2 : null,
    conversion_rate: index < 5 ? 2 : null,
  })),
  time_to_fill: { days: null, sample_count: 0, excluded_count: 1 },
  stage_duration: Object.fromEntries(
    stages.map((stage) => [stage, { days: null, sample_count: 0, excluded_count: 0 }]),
  ) as Metrics["stage_duration"],
  placement_revenue: { amount: 0, known_count: 1, missing_count: 1 },
  ai_agreement: {
    agree: rate === null ? 0 : 4,
    disagree: rate === null ? 0 : 1,
    total: rate === null ? 0 : 5,
    rate,
  },
  activities: Object.fromEntries(
    activityTypes.map((activity) => [activity, 0]),
  ) as Metrics["activities"],
});
let empty = false;
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<Reports />, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}
function reportTable() {
  return screen.getByRole("table", { name: t("reports.recruiters") });
}
function requestPaths() {
  return vi.mocked(api).mock.calls.map(([path]) => path);
}
function dates(from: string, through: string) {
  fireEvent.change(screen.getByLabelText(t("reports.from")), { target: { value: from } });
  fireEvent.change(screen.getByLabelText(t("reports.through")), { target: { value: through } });
}
beforeEach(() => {
  empty = false;
  auth.user = { id: "mine", role: "recruiter" };
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path) => {
    const url = new URL(path, "http://localhost");
    const params = url.searchParams;
    if (url.pathname === "/jobs")
      return {
        items: [
          {
            id: params.get("page") === "1" ? "job-a" : "job-b",
            title: params.get("page") === "1" ? "Việc giả A" : "Việc giả B",
            hiring_unit_id: params.get("page") === "1" ? "unit-a" : "unit-b",
            hiring_unit_name: params.get("page") === "1" ? "Đơn vị giả A" : "Đơn vị giả B",
          },
        ],
        total: 2,
      };
    const own = params.get("recruiter_id");
    const metrics = metric(
      empty ? 0 : own === "mine" ? 2 : own === "other" ? 11 : 1200,
      empty ? null : 0.8,
    );
    const period = {
      from_date: params.get("from"),
      to_date: params.get("to"),
      timezone: "Asia/Ho_Chi_Minh",
      as_of: "2026-11-09T02:00:00Z",
      definition_status: "draft",
      recruiter_id: own,
      job_id: params.get("job_id"),
      hiring_unit_id: params.get("hiring_unit_id"),
    };
    if (url.pathname === "/reports/summary")
      return {
        period,
        metrics,
        new_cvs_by_day: [{ date: params.get("from"), count: metrics.new_cvs }],
      };
    if (url.pathname === "/reports/funnel")
      return {
        period,
        stages: empty
          ? metrics.funnel.map((row) => ({ ...row, count: 0, conversion_rate: null }))
          : metrics.funnel,
      };
    if (url.pathname === "/reports/ai-agreement")
      return { period, agreement: metrics.ai_agreement };
    if (url.pathname === "/reports/recruiters")
      return {
        period,
        items: [
          { recruiter_id: "mine", recruiter_name: "Người giả A", metrics: metric(2, null) },
          { recruiter_id: "other", recruiter_name: "Người giả B", metrics: metric(11) },
          { recruiter_id: null, recruiter_name: null, metrics: metric(0) },
        ].filter((row) => !own || row.recruiter_id === own),
      };
    if (url.pathname === "/reports/export.xlsx") return new Blob(["synthetic workbook"]);
    throw new Error(`Unexpected mock request ${url.pathname}`);
  });
});

it("limits a recruiter to own totals and own row, including all scoped Job option pages", async () => {
  show();
  expect(await screen.findByText("Người giả A")).toBeVisible();
  expect(within(reportTable()).getAllByRole("row")).toHaveLength(2);
  expect(screen.queryByText("Người giả B")).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: t("reports.recruiter") })).not.toBeInTheDocument();
  expect(screen.getByText(t("reports.ownScope"))).toBeVisible();
  expect(
    within(within(reportTable()).getAllByRole("row")[1]).getAllByRole("cell")[1],
  ).toHaveTextContent(/^2$/);
  expect(
    within(screen.getByRole("region", { name: t("reports.metrics") })).queryByText("1.200"),
  ).not.toBeInTheDocument();
  await waitFor(() =>
    expect(screen.getByRole("option", { name: "Việc giả B" })).toBeInTheDocument(),
  );
  const requests = requestPaths().filter((path) => path.startsWith("/reports/"));
  expect(requests).toHaveLength(4);
  expect(
    requests.every(
      (path) => new URL(path, "http://localhost").searchParams.get("recruiter_id") === "mine",
    ),
  ).toBe(true);
  expect(requestPaths()).not.toContain("/jobs/options");
});

it.each(["lead", "admin"])(
  "shows team totals and sortable rows for %s without averaging personal rates",
  async (role) => {
    auth.user!.role = role;
    const user = userEvent.setup();
    show();
    await screen.findByRole("table", { name: t("reports.recruiters") });
    expect(within(reportTable()).getAllByRole("row")).toHaveLength(4);
    expect(
      within(screen.getByRole("region", { name: t("reports.metrics") })).getByText("1.200"),
    ).toBeVisible();
    expect(
      within(screen.getByRole("region", { name: t("reports.agreement") })).getByText("80,0%"),
    ).toBeVisible();
    const column = within(reportTable()).getByRole("button", {
      name: t("reports.new_cvs"),
    });
    await user.click(column);
    await user.click(column);
    expect(within(reportTable()).getAllByRole("row")[1]).toHaveTextContent("Người giả B");
    expect(column.closest("th")).toHaveAttribute("aria-sort", "descending");
    const agreement = within(reportTable()).getByRole("button", { name: t("reports.agreement") });
    await user.click(agreement);
    await user.click(agreement);
    expect(within(reportTable()).getAllByRole("row").at(-1)).toHaveTextContent("Người giả A");
    expect(screen.getByText(t("reports.draft"))).toBeVisible();
  },
);

it("applies intersecting filters to every panel and downloads Excel with the same period and scope", async () => {
  auth.user!.role = "lead";
  const user = userEvent.setup();
  const create = vi.fn(() => "blob:report");
  const revoke = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke }));
  const downloads: string[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloads.push(this.download);
  });
  show();
  await screen.findByRole("table", { name: t("reports.recruiters") });
  dates("2026-11-01", "2026-11-03");
  expect(screen.getByRole("button", { name: t("ranking.export") })).toBeDisabled();
  expect(screen.getByText(t("reports.unapplied"))).toBeVisible();
  await user.selectOptions(screen.getByLabelText(t("reports.recruiter")), "other");
  await user.selectOptions(screen.getByLabelText(t("reports.unit")), "unit-b");
  expect(screen.queryByRole("option", { name: "Việc giả A" })).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText(t("reports.job")), "job-b");
  await user.click(screen.getByRole("button", { name: t("reports.apply") }));
  await waitFor(() => expect(within(reportTable()).getAllByRole("row")).toHaveLength(2));
  await user.click(screen.getByRole("button", { name: t("ranking.export") }));
  await waitFor(() => expect(downloads).toEqual(["bao-cao-2026-11-01-2026-11-04.xlsx"]));
  const suffix =
    "from=2026-11-01&to=2026-11-04&recruiter_id=other&job_id=job-b&hiring_unit_id=unit-b";
  for (const endpoint of ["summary", "funnel", "recruiters", "ai-agreement", "export.xlsx"])
    expect(requestPaths()).toContain(`/reports/${endpoint}?${suffix}`);
  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:report"), { timeout: 2000 });
  expect(create).toHaveBeenCalledOnce();
});

it("rejects missing, reversed and overlong dates without requesting a report", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByText("Người giả A");
  const before = requestPaths().length;
  for (const [from, through] of [
    ["", "2026-11-01"],
    ["2026-11-04", "2026-11-01"],
    ["2025-01-01", "2026-01-02"],
  ]) {
    dates(from, through);
    await user.click(screen.getByRole("button", { name: t("reports.apply") }));
    expect(screen.getByRole("alert")).toHaveTextContent(t("reports.invalidPeriod"));
    expect(screen.getByLabelText(t("reports.from"))).toHaveFocus();
  }
  expect(requestPaths()).toHaveLength(before);
});

it("uses Vietnamese calendar presets and validates leap dates and the inclusive 366 day limit", () => {
  const now = new Date("2026-10-31T18:00:00Z");
  expect(presetDates("today", now)).toEqual({ from: "2026-11-01", through: "2026-11-01" });
  expect(presetDates("week", now)).toEqual({ from: "2026-10-26", through: "2026-11-01" });
  expect(presetDates("month", new Date("2026-11-08T18:00:00Z"))).toEqual({
    from: "2026-11-01",
    through: "2026-11-09",
  });
  expect(validPeriod("2024-01-01", "2024-12-31")).toBe(true);
  expect(validPeriod("2024-01-01", "2025-01-01")).toBe(false);
  expect(validPeriod("2026-02-29", "2026-03-01")).toBe(false);
  expect(validPeriod("0001-01-01", "0001-01-02")).toBe(false);
  expect(validPeriod("2026-11-01", "2026-11-01")).toBe(true);
  expect(reportRate(0)).toBe("0,0%");
  expect(reportRate(1.25)).toBe("125,0%");
  expect(reportNumber(1234.5)).toBe("1.234,5");
  expect(reportRate(null)).toBe(t("reports.undefined"));
  const filters: ReportFilters = {
    from: "2024-02-29",
    through: "2024-02-29",
    recruiter: "other",
    job: "",
    unit: "",
  };
  expect(reportParams(filters, "mine")).toBe("from=2024-02-29&to=2024-03-01&recruiter_id=mine");
});

it("distinguishes empty charts, missing medians and agreement from zero fees, and does not cap flow ratios", async () => {
  empty = true;
  show();
  await screen.findByText(t("reports.noCVs"));
  expect(screen.getByText(t("reports.noFlow"))).toBeVisible();
  expect(
    within(screen.getByRole("region", { name: t("reports.agreement") })).getByText(
      t("reports.undefined"),
    ),
  ).toBeVisible();
  const cards = screen.getByRole("region", { name: t("reports.metrics") });
  expect(within(cards).getByText(t("reports.undefined"))).toBeVisible();
  expect(within(cards).getByText("0 ₫")).toBeVisible();
});

it("retains flow rates above 100 percent and renders charts with a textual data alternative", async () => {
  show();
  await screen.findByText("Người giả A");
  const funnel = screen.getByRole("region", { name: t("reports.funnel") });
  expect(within(funnel).getAllByText("200,0%")).toHaveLength(5);
  expect(funnel.querySelector("svg")).not.toBeNull();
  fireEvent.click(screen.getByText(t("reports.dailyTable"), { selector: "summary" }));
  expect(screen.getByRole("table", { name: t("reports.dailyTable") })).toBeVisible();
});

it("hides stale totals after a failed refresh and retries without losing the filters", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByText("Người giả A");
  const original = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation((path, options) =>
    path.startsWith("/reports/summary")
      ? Promise.reject(new ApiError(403, "FORBIDDEN", t("api.forbidden")))
      : original(path, options),
  );
  await user.click(screen.getByRole("button", { name: t("reports.apply") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.forbidden"));
  expect(screen.queryByRole("region", { name: t("reports.metrics") })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: t("ranking.export") })).toBeDisabled();
  vi.mocked(api).mockImplementation(original);
  await user.click(screen.getByRole("button", { name: t("common.retry") }));
  expect(await screen.findByText("Người giả A")).toBeVisible();
});

it("cancels outdated report requests on filter changes and ignores late responses", async () => {
  const original = vi.mocked(api).getMockImplementation()!;
  let resolve!: (value: unknown) => void;
  let oldSignal: AbortSignal | null | undefined;
  vi.mocked(api).mockImplementation((path, options) => {
    if (path.startsWith("/reports/summary") && !path.includes("from=2024-01-01")) {
      oldSignal = options?.signal;
      return new Promise((done) => {
        resolve = done;
      });
    }
    return original(path, options);
  });
  const user = userEvent.setup();
  show();
  await screen.findByRole("option", { name: "Việc giả B" });
  dates("2024-01-01", "2024-01-01");
  await user.click(screen.getByRole("button", { name: t("reports.apply") }));
  await screen.findByText("Người giả A");
  expect(oldSignal?.aborted).toBe(true);
  resolve({ metrics: metric(999999) });
  await waitFor(() => expect(screen.getByText(/01\/01\/2024.*01\/01\/2024/)).toBeVisible());
  expect(screen.queryByText("999.999")).not.toBeInTheDocument();
});

it("prevents duplicate exports and suppresses a download after unmount", async () => {
  const user = userEvent.setup();
  const original = vi.mocked(api).getMockImplementation()!;
  let resolve!: (value: Blob) => void;
  let signal: AbortSignal | null | undefined;
  const create = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create }));
  vi.mocked(api).mockImplementation((path, options) => {
    if (path.startsWith("/reports/export.xlsx")) {
      signal = options?.signal;
      return new Promise((done) => {
        resolve = done;
      });
    }
    return original(path, options);
  });
  const view = show();
  await screen.findByText("Người giả A");
  await user.dblClick(screen.getByRole("button", { name: t("ranking.export") }));
  expect(screen.getByRole("button", { name: t("ranking.exporting") })).toBeDisabled();
  expect(requestPaths().filter((path) => path.startsWith("/reports/export.xlsx"))).toHaveLength(1);
  expect(new URL(requestPaths().at(-1)!, "http://localhost").searchParams.get("recruiter_id")).toBe(
    "mine",
  );
  view.unmount();
  expect(signal?.aborted).toBe(true);
  resolve(new Blob(["synthetic"]));
  await Promise.resolve();
  expect(create).not.toHaveBeenCalled();
});

it("drops the team view and filters when the session changes to recruiter", async () => {
  auth.user!.role = "lead";
  const view = show();
  await screen.findByRole("table", { name: t("reports.recruiters") });
  expect(within(reportTable()).getAllByRole("row")).toHaveLength(4);
  auth.user = { id: "mine", role: "recruiter" };
  // Rerender with the same query cache to prove role-specific keys cannot reuse team data.
  view.rerender(<Reports />);
  await waitFor(() => expect(within(reportTable()).getAllByRole("row")).toHaveLength(2));
  expect(screen.queryByRole("combobox", { name: t("reports.recruiter") })).not.toBeInTheDocument();
});

it("keeps loaded reports when filter options fail and supports retrying those options", async () => {
  const user = userEvent.setup();
  const original = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation((path, options) =>
    path.startsWith("/jobs?")
      ? Promise.reject(new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable")))
      : original(path, options),
  );
  show();
  await screen.findByText("Người giả A");
  expect(screen.getByRole("alert")).toHaveTextContent(t("api.unavailable"));
  expect(screen.getByLabelText(t("reports.job"))).toBeDisabled();
  vi.mocked(api).mockImplementation(original);
  await user.click(screen.getByRole("button", { name: t("common.retry") }));
  expect(await screen.findByRole("option", { name: "Việc giả B" })).toBeInTheDocument();
  expect(screen.getByLabelText(t("reports.job"))).toBeEnabled();
});

it("shows a safe export error and lets the user retry the same report", async () => {
  const user = userEvent.setup();
  const original = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation((path, options) =>
    path.startsWith("/reports/export.xlsx")
      ? Promise.reject(new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable")))
      : original(path, options),
  );
  show();
  await screen.findByText("Người giả A");
  await user.click(screen.getByRole("button", { name: t("ranking.export") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  expect(screen.getByRole("button", { name: t("ranking.export") })).toBeEnabled();
  await user.click(screen.getByRole("button", { name: t("ranking.export") }));
  await waitFor(() =>
    expect(requestPaths().filter((path) => path.startsWith("/reports/export.xlsx"))).toHaveLength(
      2,
    ),
  );
  expect(within(reportTable()).getAllByRole("row")).toHaveLength(2);
});
