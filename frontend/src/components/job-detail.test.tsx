import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { JobDetail } from "@/components/job-detail";
import { CvUpload } from "@/components/cv-upload";
import { api, ApiError } from "@/lib/api";
import { t } from "@/i18n/vi";
import type { RankedApplication, Ranking } from "@/lib/ranking-types";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
const counts = { high: 3, medium: 1, low: 6, insufficient: 0, pending: 0, running: 0, failed: 0 };
const rows: RankedApplication[] = Array.from({ length: 10 }, (_, index) => ({
  id: `app-${index}`,
  candidate_id: `candidate-${index}`,
  candidate_name: `Ứng viên giả ${index}`,
  skills: ["python", "sql"],
  years_experience: index === 0 ? null : "3.50",
  stage: "new",
  ai_status: "done",
  ai_level: index < 3 ? "high" : index === 3 ? "medium" : "low",
  created_at: "2026-11-08T01:00:00Z",
}));
const ranking: Ranking = { items: rows, total: 10, ai_counts: counts };

function show(component = <JobDetail jobId="job" />) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{component}</QueryClientProvider>);
}
beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/jobs/job")
      return {
        id: "job",
        title: "Job mẫu giả",
        hiring_unit_name: "Đơn vị giả",
        owner_name: "HR giả",
        description: "Mô tả giả",
        must_have: ["Python"],
        nice_to_have: [],
      };
    if (path.startsWith("/jobs/job/applications")) return ranking;
    throw new Error("Unexpected mocked API path");
  });
});

it("renders ten ranked rows, six columns, no numeric scores and an accessible drawer", async () => {
  show();
  await screen.findByRole("button", { name: rows[0].candidate_name });
  expect(screen.getAllByRole("columnheader")).toHaveLength(6);
  expect(screen.getAllByRole("row")).toHaveLength(11);
  expect(
    screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[1].textContent),
  ).toEqual([...Array(3).fill(t("ai.high")), t("ai.medium"), ...Array(6).fill(t("ai.low"))]);
  expect(within(screen.getAllByRole("row")[1]).getAllByRole("cell")[3]).toHaveTextContent(
    t("ranking.unknown"),
  );
  const trigger = screen.getByRole("button", { name: rows[0].candidate_name });
  await userEvent.click(trigger);
  expect(screen.getByRole("dialog")).toHaveAccessibleName(rows[0].candidate_name);
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(trigger).toHaveFocus();
  await userEvent.click(screen.getByRole("tab", { name: t("ranking.info") }));
  expect(screen.getByText("Mô tả giả")).toBeVisible();
});

it("confirms the personal data warning before downloading the Job workbook", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  const downloads: string[] = [];
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloads.push(this.download);
  });
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:export"),
    revokeObjectURL: vi.fn(),
  });
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/jobs/job")
      return {
        id: "job",
        title: "Job mẫu giả",
        hiring_unit_name: "Đơn vị giả",
        owner_name: "HR giả",
        description: "Mô tả giả",
        must_have: [],
        nice_to_have: [],
      };
    if (path.startsWith("/jobs/job/applications")) return ranking;
    if (path === "/jobs/job/export.xlsx") return new Blob(["fake workbook"]);
    throw new Error("Unexpected mocked API path");
  });
  show();
  await userEvent.click(await screen.findByRole("button", { name: t("ranking.export") }));
  expect(confirm).toHaveBeenCalledWith(t("ranking.exportWarning"));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/jobs/job/export.xlsx", { responseType: "blob" }));
  expect(click).toHaveBeenCalledOnce();
  expect(downloads[0]).toMatch(/^ung-vien-job-mau-gia-\d{4}-\d{2}-\d{2}\.xlsx$/);
  confirm.mockRestore();
  click.mockRestore();
  vi.unstubAllGlobals();
});

it("sends level, stage and search filters to the API and shows an actionable empty state", async () => {
  show();
  await screen.findByRole("table");
  await userEvent.selectOptions(screen.getByLabelText(t("ranking.level")), "high");
  await userEvent.selectOptions(screen.getByLabelText(t("ranking.stage")), "interview");
  await userEvent.type(screen.getByLabelText(t("ranking.search")), "SQL");
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      expect.stringContaining("q=SQL&ai_level=high&stage=interview"),
      expect.anything(),
    ),
  );
});

it("shows empty, failed-score and loading error states with retry", async () => {
  vi.mocked(api).mockRejectedValueOnce(new ApiError(403, "FORBIDDEN", t("api.forbidden")));
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.forbidden"));
  await userEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  await screen.findByRole("table");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("keeps batch errors on the correct filename while polling reading, scoring and completion every 3s", async () => {
  let statusCalls = 0;
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/cv-files") {
      const body = options?.body as FormData;
      expect(body.get("job_id")).toBe("job");
      expect(body.getAll("files")).toHaveLength(2);
      return {
        items: [
          {
            index: 1,
            error: { code: "INVALID_FILE_TYPE", message: "SYNTHETIC_PRIVATE_ERROR" },
            cv_file: null,
            duplicate: false,
          },
          {
            index: 0,
            error: null,
            cv_file: { id: "file", job_id: "job", status: "pending" },
            duplicate: false,
          },
        ],
      };
    }
    if (path === "/cv-files/file") {
      statusCalls++;
      return {
        id: "file",
        job_id: "job",
        status: statusCalls === 1 ? "pending" : "done",
        application_id: statusCalls > 1 ? "app" : null,
        ai_status: statusCalls < 2 ? null : statusCalls === 2 ? "pending" : "done",
        processing_error: null,
      };
    }
    throw new Error("Unexpected mocked path");
  });
  show(<CvUpload jobId="job" />);
  fireEvent.drop(screen.getByText(t("upload.drop")).parentElement!, {
    dataTransfer: {
      files: [new File(["synthetic"], "valid.pdf"), new File(["synthetic"], "bad.exe")],
    },
  });
  const list = await screen.findByRole("list", { name: t("upload.progress") });
  const bad = within(list).getByText("bad.exe").closest("li")!;
  await waitFor(() =>
    expect(within(bad).getByRole("alert")).toHaveTextContent(t("upload.invalidType")),
  );
  const good = within(list).getByText("valid.pdf").closest("li")!;
  expect(within(good).getByRole("status")).toHaveTextContent(t("upload.reading"));
  await waitFor(
    () => expect(within(good).getByRole("status")).toHaveTextContent(t("upload.scoring")),
    { timeout: 4500 },
  );
  expect(statusCalls).toBe(2);
  await waitFor(
    () => expect(within(good).getByRole("status")).toHaveTextContent(t("upload.done")),
    { timeout: 4500 },
  );
  expect(statusCalls).toBe(3);
  expect(within(bad).getByRole("alert")).toHaveTextContent(t("upload.invalidType"));
  expect(screen.queryByText("SYNTHETIC_PRIVATE_ERROR")).not.toBeInTheDocument();
}, 12000);

it("shows a worker failure and polling failure independently, then retries only that status", async () => {
  let failed = true;
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/cv-files")
      return {
        items: [0, 1].map((index) => ({
          index,
          cv_file: { id: `f${index}`, job_id: "job", status: "pending" },
          error: null,
          duplicate: false,
        })),
      };
    if (path === "/cv-files/f0") return { status: "failed", ai_status: null };
    if (failed) throw new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable"));
    return { status: "done", ai_status: "done" };
  });
  show(<CvUpload jobId="job" />);
  await userEvent.upload(screen.getByLabelText(t("upload.title"), { selector: "input" }), [
    new File(["x"], "worker.pdf"),
    new File(["x"], "poll.pdf"),
  ]);
  await screen.findByText(t("upload.statusFailed"));
  expect(screen.getByText(t("upload.readFailed"))).toBeVisible();
  failed = false;
  await userEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  await screen.findByText(t("upload.done"));
  expect(screen.getByText(t("upload.readFailed"))).toBeVisible();
});

it("reports duplicates from another Job without polling or silently creating an application", async () => {
  vi.mocked(api).mockResolvedValue({
    items: [
      {
        index: 0,
        cv_file: { id: "dup", job_id: "other", status: "done" },
        duplicate: true,
        error: null,
      },
    ],
  });
  show(<CvUpload jobId="job" />);
  await userEvent.upload(
    screen.getByLabelText(t("upload.title"), { selector: "input" }),
    new File(["x"], "dup.pdf"),
  );
  await screen.findByText(t("upload.duplicateOther"));
  expect(screen.getByText(t("upload.duplicate"))).toBeVisible();
  expect(api).toHaveBeenCalledTimes(1);
});

it("rejects batches above 50 files and localizes a failed HTTP request on each row", async () => {
  vi.mocked(api).mockRejectedValue(new Error("SYNTHETIC_PRIVATE_ERROR"));
  show(<CvUpload jobId="job" />);
  const input = screen.getByLabelText(t("upload.title"), { selector: "input" });
  await userEvent.upload(
    input,
    Array.from({ length: 51 }, (_, i) => new File(["x"], `fake${i}.pdf`)),
  );
  expect(screen.getAllByText(t("upload.tooMany"))).toHaveLength(51);
  expect(api).not.toHaveBeenCalled();
  await userEvent.upload(input, new File(["x"], "network.pdf"));
  await screen.findByText(t("upload.failed"));
  expect(screen.queryByText("SYNTHETIC_PRIVATE_ERROR")).not.toBeInTheDocument();
});

it.each([
  ["failed", "upload.aiFailed"],
  [null, "upload.noApplication"],
] as const)("shows a terminal %s assessment on the correct upload row", async (status, key) => {
  vi.mocked(api).mockImplementation(async (path) =>
    path === "/cv-files"
      ? {
          items: [
            {
              index: 0,
              cv_file: { id: "file", job_id: "job", status: "done" },
              error: null,
              duplicate: false,
            },
          ],
        }
      : { status: "done", ai_status: status },
  );
  show(<CvUpload jobId="job" />);
  await userEvent.upload(
    screen.getByLabelText(t("upload.title"), { selector: "input" }),
    new File(["x"], "terminal.pdf"),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(t(key));
});

it("uses a fresh status when a previously failed SHA duplicate is uploaded again", async () => {
  let successful = false;
  vi.mocked(api).mockImplementation(async (path) =>
    path === "/cv-files"
      ? {
          items: [
            {
              index: 0,
              cv_file: { id: "file", job_id: "job", status: "failed" },
              error: null,
              duplicate: true,
            },
          ],
        }
      : { status: successful ? "done" : "failed", ai_status: successful ? "done" : null },
  );
  show(<CvUpload jobId="job" />);
  const input = screen.getByLabelText(t("upload.title"), { selector: "input" });
  const file = new File(["x"], "retry.pdf");
  await userEvent.upload(input, file);
  await screen.findByText(t("upload.readFailed"));
  successful = true;
  await userEvent.upload(input, file);
  await waitFor(() => expect(screen.getAllByText(t("upload.done"))).toHaveLength(2));
  expect(screen.queryByText(t("upload.readFailed"))).not.toBeInTheDocument();
});
