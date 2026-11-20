import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { JobEditor, JobForm } from "@/components/job-form";
import { api, ApiError } from "@/lib/api";
import type { Job, JobOptions } from "@/lib/job-types";
import { t } from "@/i18n/vi";

const state = vi.hoisted(() => ({ push: vi.fn(), role: "admin" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: state.push }) }));
vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({ user: { id: "owner", role: state.role } }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));

const options: JobOptions = {
  hiring_units: [{ id: "unit", name: "Đơn vị giả" }],
  users: [
    { id: "owner", name: "Người phụ trách giả" },
    { id: "member", name: "Thành viên giả" },
  ],
};
const job: Job = {
  id: "job",
  title: "Việc giả",
  description: "Mô tả giả",
  must_have: ["Python"],
  nice_to_have: [],
  member_ids: [],
  owner_id: "owner",
  owner_name: "Người phụ trách giả",
  hiring_unit_id: "unit",
  hiring_unit_name: "Đơn vị giả",
  status: "open",
  location: null,
  employment_type: null,
  salary_min: null,
  salary_max: null,
  headcount: 1,
  deadline: null,
  opened_at: null,
  closed_at: null,
  needs_rescore: false,
};

function show(existing?: Job) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <JobForm options={options} job={existing} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api).mockReset();
  state.push.mockReset();
  state.role = "admin";
});

it("shows a Vietnamese title error, focuses the field and does not submit an empty form", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  expect(screen.getByText(t("jobs.titleRequired"))).toHaveAttribute("role", "alert");
  expect(screen.getByLabelText(t("jobs.title"))).toHaveFocus();
  expect(api).not.toHaveBeenCalled();
});

it("rejects whitespace-only titles", async () => {
  show();
  await userEvent.type(screen.getByLabelText(t("jobs.title")), "   ");
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  expect(screen.getByText(t("jobs.titleRequired"))).toBeVisible();
  expect(api).not.toHaveBeenCalled();
});

it("validates the salary interval and mandatory requirements in Vietnamese", async () => {
  show({ ...job, salary_min: 20, salary_max: 10, must_have: [] });
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  expect(screen.getByText(t("jobs.salaryInvalid"))).toBeVisible();
  expect(screen.getByText(t("jobs.mustRequired"))).toBeVisible();
  expect(api).not.toHaveBeenCalled();
});

it("creates a Job with two requirement lists and members in one request", async () => {
  show();
  vi.mocked(api).mockResolvedValue({ ...job, needs_rescore: false });
  await userEvent.type(screen.getByLabelText(t("jobs.title")), "Việc mới giả");
  await userEvent.selectOptions(screen.getByLabelText(t("jobs.unit")), "unit");
  await userEvent.type(screen.getByLabelText(t("jobs.must_have")), " Python \nSQL");
  await userEvent.type(screen.getByLabelText(t("jobs.nice_to_have")), "Git");
  await userEvent.click(screen.getByRole("checkbox", { name: "Thành viên giả" }));
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  await waitFor(() => expect(state.push).toHaveBeenCalledWith("/jobs"));
  expect(api).toHaveBeenCalledTimes(1);
  const [path, request] = vi.mocked(api).mock.calls[0];
  expect(path).toBe("/jobs");
  expect(request?.method).toBe("POST");
  expect(JSON.parse(request?.body as string)).toMatchObject({
    title: "Việc mới giả",
    must_have: ["Python", "SQL"],
    nice_to_have: ["Git"],
    member_ids: ["member"],
    owner_id: "owner",
  });
});

it("asks about rescoring after saving, and cancellation keeps old scores", async () => {
  show(job);
  vi.mocked(api).mockResolvedValue({ ...job, needs_rescore: true });
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  expect(await screen.findByRole("dialog", { name: t("jobs.rescoreTitle") })).toBeVisible();
  expect(state.push).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: t("common.cancel") }));
  expect(api).toHaveBeenCalledTimes(1);
  expect(state.push).toHaveBeenCalledWith("/jobs");
});

it("queues rescoring only after confirmation and permits retry after queue failure", async () => {
  show(job);
  vi.mocked(api)
    .mockResolvedValueOnce({ ...job, needs_rescore: true })
    .mockRejectedValueOnce(new ApiError(503, "AI_QUEUE_UNAVAILABLE", t("api.unavailable")))
    .mockResolvedValueOnce({ status: "pending" });
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  await screen.findByRole("dialog");
  expect(api).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: t("jobs.rescoreConfirm") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("common.confirmError"));
  expect(state.push).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: t("jobs.rescoreConfirm") }));
  await waitFor(() => expect(state.push).toHaveBeenCalledWith("/jobs"));
  expect(api).toHaveBeenNthCalledWith(2, "/jobs/job/rescore", { method: "POST" });
});

it("preserves entered fields when saving fails", async () => {
  show(job);
  vi.mocked(api).mockRejectedValue(
    new ApiError(503, "EMBEDDING_UNAVAILABLE", t("api.unavailable")),
  );
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  expect(screen.getByLabelText(t("jobs.title"))).toHaveValue(job.title);
  expect(state.push).not.toHaveBeenCalled();
});

it("keeps the original owner when a recruiter edits a member Job", async () => {
  state.role = "recruiter";
  show({ ...job, owner_id: "member", owner_name: "Thành viên giả" });
  vi.mocked(api).mockResolvedValue(job);
  expect(screen.getByLabelText(t("jobs.owner"))).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: t("jobs.save") }));
  await waitFor(() => expect(api).toHaveBeenCalled());
  expect(JSON.parse(vi.mocked(api).mock.calls[0][1]?.body as string).owner_id).toBe("member");
});

it("shows loading and retry after option loading fails", async () => {
  vi.mocked(api).mockRejectedValue(new ApiError(0, "NETWORK_ERROR", t("api.network")));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <JobEditor />
    </QueryClientProvider>,
  );
  expect(screen.getByRole("status")).toHaveTextContent(t("common.loading"));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.network"));
  expect(screen.queryByRole("button", { name: t("jobs.save") })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
});
