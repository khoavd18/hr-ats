import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { MyTasks } from "@/components/task-list";
import { TaskCreateDialog } from "@/components/task-create-dialog";
import { Overview } from "@/components/overview";
import { api, ApiError } from "@/lib/api";
import { taskGroup, type Task } from "@/lib/task-types";
import { t } from "@/i18n/vi";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
let rows: Task[];
function show(element: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
}
const row = (id: string, due_at: string | null): Task => ({
  id,
  title: `Việc giả ${id}`,
  due_at,
  description: null,
  assignee_id: "me",
  created_by: "me",
  job_id: null,
  application_id: null,
  status: "todo",
  completed_at: null,
});
beforeEach(() => {
  vi.mocked(api).mockReset();
  rows = [row("one", null)];
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.startsWith("/tasks?")) return { items: rows, total: rows.length };
    if (path === "/auth/me") return { id: "me", role: "lead" };
    if (path === "/jobs/options")
      return { users: [{ id: "other", name: "Người nhận giả" }], hiring_units: [] };
    if (path.startsWith("/jobs?"))
      return { items: [{ id: "job", title: "Việc tuyển giả" }], total: 1 };
    if (path.startsWith("/tasks/application-options"))
      return { items: [{ id: "app", name: "Ứng viên giả" }], total: 1 };
    if (path.startsWith("/tasks/") && options?.method === "PATCH") {
      rows = [];
      return {};
    }
    if (path === "/tasks" && options?.method === "POST") return {};
    throw new Error(`Unexpected mocked path: ${path}`);
  });
});

it("groups dates by Vietnamese calendar days independently of the host timezone", () => {
  const now = new Date("2026-11-08T18:00:00Z"); // Nov 9 in Vietnam.
  expect(taskGroup(row("a", "2026-11-08T16:59:59Z"), now)).toBe("overdue");
  expect(taskGroup(row("a", "2026-11-08T17:00:00Z"), now)).toBe("today");
  expect(taskGroup(row("a", "2026-11-09T16:59:59Z"), now)).toBe("today");
  expect(taskGroup(row("a", "2026-11-09T17:00:00Z"), now)).toBe("upcoming");
  expect(taskGroup(row("a", null), now)).toBe("upcoming");
});

it("ticks completion, refreshes the list and retains a task when saving fails", async () => {
  const user = userEvent.setup();
  const original = vi.mocked(api).getMockImplementation()!;
  let fail = true;
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.startsWith("/tasks/") && fail) {
      fail = false;
      throw new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable"));
    }
    return original(path, options);
  });
  show(<MyTasks />);
  const checkbox = await screen.findByRole("checkbox", {
    name: t("tasks.complete").replace("{title}", "Việc giả one"),
  });
  await user.click(checkbox);
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  expect(checkbox).not.toBeChecked();
  await user.click(checkbox);
  await waitFor(() => expect(screen.queryByRole("checkbox")).not.toBeInTheDocument());
  expect(api).toHaveBeenCalledWith(
    "/tasks/one",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ status: "done" }) }),
  );
});

it("creates a task linked to a Job and candidate with a Vietnam offset", async () => {
  const user = userEvent.setup();
  show(<TaskCreateDialog />);
  await user.click(screen.getByRole("button", { name: t("tasks.create") }));
  const dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByLabelText(t("tasks.title")), "Việc giả mới");
  await user.type(within(dialog).getByLabelText(t("tasks.due")), "2026-11-10T08:00");
  await user.selectOptions(within(dialog).getByLabelText(t("tasks.assignee")), "other");
  await user.selectOptions(within(dialog).getByLabelText(t("tasks.job")), "job");
  await within(dialog).findByRole("option", { name: "Ứng viên giả" });
  await user.selectOptions(within(dialog).getByLabelText(t("tasks.candidate")), "app");
  await user.click(within(dialog).getByRole("button", { name: t("common.save") }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  const call = vi
    .mocked(api)
    .mock.calls.find(([path, options]) => path === "/tasks" && options?.method === "POST")!;
  expect(JSON.parse(call[1]!.body as string)).toMatchObject({
    title: "Việc giả mới",
    due_at: "2026-11-10T08:00:00+07:00",
    assignee_id: "other",
    job_id: "job",
    application_id: "app",
  });
});

it("keeps input on failure and locks duplicate submits and closing during save", async () => {
  const user = userEvent.setup();
  const original = vi.mocked(api).getMockImplementation()!;
  let reject!: (error: Error) => void;
  vi.mocked(api).mockImplementation((path, options) =>
    path === "/tasks"
      ? new Promise((_, no) => {
          reject = no;
        })
      : original(path, options),
  );
  show(<TaskCreateDialog applicationId="profile" />);
  await user.click(screen.getByRole("button", { name: t("tasks.create") }));
  await user.type(screen.getByLabelText(t("tasks.title")), "Giữ việc giả");
  await waitFor(() => expect(screen.getByRole("button", { name: t("common.save") })).toBeEnabled());
  await user.dblClick(screen.getByRole("button", { name: t("common.save") }));
  expect(screen.getByRole("button", { name: t("common.processing") })).toBeDisabled();
  await user.keyboard("{Escape}");
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(vi.mocked(api).mock.calls.filter(([path]) => path === "/tasks")).toHaveLength(1);
  reject(new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable")));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  expect(screen.getByLabelText(t("tasks.title"))).toHaveValue("Giữ việc giả");
  const payload = JSON.parse(
    vi.mocked(api).mock.calls.find(([path]) => path === "/tasks")![1]!.body as string,
  );
  expect(payload.application_id).toBe("profile");
  expect(screen.queryByLabelText(t("tasks.job"))).not.toBeInTheDocument();
});

it("cancels without creating a task", async () => {
  const user = userEvent.setup();
  show(<TaskCreateDialog />);
  await user.click(screen.getByRole("button", { name: t("tasks.create") }));
  await user.click(screen.getByRole("button", { name: t("common.cancel") }));
  expect(vi.mocked(api).mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
});

it("renders overview totals, upcoming interviews, deadlines and the quick upload form", async () => {
  const user = userEvent.setup();
  const original = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation((path, options) =>
    path === "/overview"
      ? Promise.resolve({
          today_tasks: { items: rows, total: 1 },
          interviews: [
            {
              id: "i",
              application_id: "app",
              candidate_name: "Ứng viên giả",
              job_title: "Việc tuyển giả",
              scheduled_at: "2026-11-09T02:00:00Z",
            },
          ],
          interview_total: 1,
          jobs: [{ id: "job", title: "Việc sắp hết hạn giả", deadline: "2026-11-10" }],
          job_total: 1,
          unseen_cv_count: 3,
        })
      : original(path, options),
  );
  show(<Overview />);
  expect(await screen.findByRole("region", { name: t("overview.unseen") })).toHaveTextContent("3");
  expect(screen.getByRole("region", { name: t("overview.interviews") })).toHaveTextContent("09:00");
  expect(screen.getByRole("link", { name: "Việc sắp hết hạn giả" })).toHaveAttribute(
    "href",
    "/jobs/job",
  );
  await user.click(screen.getByRole("button", { name: t("overview.upload") }));
  expect(await screen.findByLabelText(t("overview.selectJob"))).toBeInTheDocument();
});

it("shows a retry action when task loading fails", async () => {
  const user = userEvent.setup();
  vi.mocked(api).mockRejectedValueOnce(
    new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable")),
  );
  show(<MyTasks />);
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  await user.click(screen.getByRole("button", { name: t("common.retry") }));
  expect(await screen.findByText("Việc giả one")).toBeInTheDocument();
});
