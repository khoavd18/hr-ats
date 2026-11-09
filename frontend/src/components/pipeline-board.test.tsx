import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { PipelineBoard } from "@/components/pipeline-board";
import { Toaster } from "@/components/ui/sonner";
import { api, ApiError } from "@/lib/api";
import type { MoveResult, Pipeline, PipelineCard } from "@/lib/pipeline-types";
import { stages, type Stage } from "@/lib/ranking-types";
import { t } from "@/i18n/vi";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));

const card: PipelineCard = {
  id: "app-fake",
  candidate_id: "candidate-fake",
  candidate_name: "Ứng viên giả T20",
  stage: "new",
  stage_entered_at: new Date(Date.now() - 2 * 86400000).toISOString(),
  owner_id: "owner-fake",
  ai_status: "done",
  ai_level: "high",
};
let server: Pipeline;

function changed(stage: Stage) {
  const update = { id: card.id, stage, stage_entered_at: new Date().toISOString() };
  server = {
    total: 1,
    columns: stages.map((value) => ({
      stage: value,
      total: value === stage ? 1 : 0,
      items: value === stage ? [{ ...card, ...update }] : [],
    })),
  };
  return update;
}

function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <PipelineBoard jobId="job-fake" />
      <Toaster />
    </QueryClientProvider>,
  );
  return client;
}

function column(stage: Stage) {
  return screen.getByRole("region", { name: t(`stage.${stage}`) });
}

async function dragTo(stage: Stage) {
  const handle = await screen.findByRole("button", {
    name: t("pipeline.drag").replace("{name}", card.candidate_name),
  });
  handle.focus();
  await userEvent.keyboard("[Space]");
  for (let index = 0; index < stages.indexOf(stage); index++)
    await userEvent.keyboard("[ArrowRight]");
  await userEvent.keyboard("[Space]");
}

beforeEach(() => {
  // jsdom has no pointer capture; Sonner uses the browser API on a toast button click.
  HTMLElement.prototype.setPointerCapture ??= () => {};
  changed("new");
  server.columns[0].items[0].stage_entered_at = card.stage_entered_at;
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/jobs/job-fake/pipeline") return structuredClone(server);
    if (path === "/applications/app-fake/move") {
      const body = JSON.parse(options!.body as string);
      return { application: changed(body.to_stage), suggested_email: null };
    }
    if (path === "/applications/app-fake/undo") return changed("new");
    throw new Error("Unexpected mocked API path");
  });
  // Supply browser geometry, while exercising the real dnd-kit keyboard sensor and context.
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    const section = this.closest("section[aria-label]");
    const index = stages.findIndex(
      (stage) => section?.getAttribute("aria-label") === t(`stage.${stage}`),
    );
    const left = Math.max(0, index) * 256 + (this.tagName === "LI" ? 12 : 0);
    const top = this.tagName === "LI" ? 60 : 0;
    const width = this.tagName === "LI" ? 216 : 240;
    const height = this.tagName === "LI" ? 120 : 400;
    return {
      x: left,
      y: top,
      left,
      top,
      right: left + width,
      bottom: top + height,
      width,
      height,
      toJSON: () => ({}),
    };
  });
});
afterEach(() => {
  toast.dismiss();
  vi.restoreAllMocks();
});

it("renders stage cards with AI labels and elapsed days, with withdrawn behind the menu", async () => {
  show();
  await screen.findByRole("button", { name: card.candidate_name });
  expect(within(column("new")).getByText(t("ai.high"))).toBeVisible();
  expect(within(column("new")).getByText(t("pipeline.days").replace("{days}", "2"))).toBeVisible();
  expect(screen.queryByRole("region", { name: t("stage.withdrawn") })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: t("pipeline.more") }));
  await userEvent.click(screen.getByRole("menuitemcheckbox", { name: t("stage.withdrawn") }));
  expect(column("withdrawn")).toBeVisible();
});

it("drags with real dnd-kit, calls move once and places the card optimistically before the response", async () => {
  let resolve!: (value: MoveResult) => void;
  const pending = new Promise<MoveResult>((done) => {
    resolve = done;
  });
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("/move") ? pending : structuredClone(server),
  );
  show();
  await dragTo("screening");
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/applications/app-fake/move", {
      method: "POST",
      body: JSON.stringify({ to_stage: "screening" }),
    }),
  );
  expect(
    within(column("screening")).getByRole("button", { name: card.candidate_name }),
  ).toBeVisible();
  expect(within(column("new")).queryByText(card.candidate_name)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t("pipeline.undo") })).not.toBeInTheDocument();
  await act(async () => {
    resolve({ application: changed("screening"), suggested_email: null });
  });
  expect(
    await screen.findByText(
      t("pipeline.moved")
        .replace("{name}", card.candidate_name)
        .replace("{stage}", t("stage.screening")),
    ),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: t("pipeline.undo") })).toBeVisible();
  expect(vi.mocked(api).mock.calls.filter(([path]) => path.endsWith("/move"))).toHaveLength(1);
});

it("restores the original column, counts and timestamp after an API failure and hides private errors", async () => {
  let reject!: (error: Error) => void;
  const pending = new Promise<MoveResult>((_, fail) => {
    reject = fail;
  });
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("/move") ? pending : structuredClone(server),
  );
  show();
  await dragTo("screening");
  await waitFor(() =>
    expect(within(column("screening")).getByText(card.candidate_name)).toBeVisible(),
  );
  await act(async () => {
    reject(new Error("SYNTHETIC_PRIVATE_ERROR"));
  });
  expect(await screen.findByRole("alert")).toHaveTextContent(t("pipeline.moveError"));
  expect(within(column("new")).getByText(card.candidate_name)).toBeVisible();
  expect(within(column("new")).getByText(t("pipeline.days").replace("{days}", "2"))).toBeVisible();
  expect(within(column("new")).getByRole("heading")).toHaveTextContent("1");
  expect(within(column("screening")).getByRole("heading")).toHaveTextContent("0");
  expect(screen.queryByText("SYNTHETIC_PRIVATE_ERROR")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: t("pipeline.undo") })).not.toBeInTheDocument();
});

it("undoes a successful move using the POST undo response and invalidates ranking/history", async () => {
  const client = show();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  await dragTo("screening");
  await userEvent.click(await screen.findByRole("button", { name: t("pipeline.undo") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/applications/app-fake/undo", { method: "POST" }),
  );
  expect(await screen.findByText(t("pipeline.undone"))).toBeVisible();
  expect(within(column("new")).getByText(card.candidate_name)).toBeVisible();
  expect(within(column("screening")).queryByText(card.candidate_name)).not.toBeInTheDocument();
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["job-ranking", "job-fake"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["application-profile", card.id] });
});

it("retains the moved card when undo is refused with a translated error", async () => {
  show();
  await dragTo("screening");
  await screen.findByRole("button", { name: t("pipeline.undo") });
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.endsWith("/undo")) throw new ApiError(409, "UNDO_EXPIRED", t("pipeline.undoExpired"));
    return structuredClone(server);
  });
  await userEvent.click(screen.getByRole("button", { name: t("pipeline.undo") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("pipeline.undoExpired"));
  expect(within(column("screening")).getByText(card.candidate_name)).toBeVisible();
});

it("requires a rejection reason, allows cancel, then sends the exact reason only on confirmation", async () => {
  show();
  await dragTo("rejected");
  let dialog = await screen.findByRole("dialog", { name: t("pipeline.rejectTitle") });
  expect(within(dialog).getByRole("button", { name: t("common.confirm") })).toBeDisabled();
  expect(api).not.toHaveBeenCalledWith(expect.stringContaining("/move"), expect.anything());
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(within(column("new")).getByText(card.candidate_name)).toBeVisible();
  await dragTo("rejected");
  dialog = await screen.findByRole("dialog");
  await userEvent.selectOptions(within(dialog).getByLabelText(t("pipeline.reason")), "skills");
  await userEvent.click(within(dialog).getByRole("button", { name: t("common.confirm") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/applications/app-fake/move", {
      method: "POST",
      body: JSON.stringify({ to_stage: "rejected", rejected_reason: "thiếu kỹ năng" }),
    }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(within(column("rejected")).getByText(card.candidate_name)).toBeVisible();
});

it("keeps the rejection reason on failure for retry, and blocks duplicate confirms and closing while saving", async () => {
  let reject!: (error: Error) => void;
  const pending = new Promise<MoveResult>((_, fail) => {
    reject = fail;
  });
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("/move") ? pending : structuredClone(server),
  );
  show();
  await dragTo("rejected");
  const dialog = await screen.findByRole("dialog");
  await userEvent.selectOptions(within(dialog).getByLabelText(t("pipeline.reason")), "salary");
  await userEvent.click(within(dialog).getByRole("button", { name: t("common.confirm") }));
  expect(within(dialog).getByRole("button", { name: t("common.processing") })).toBeDisabled();
  await userEvent.keyboard("{Escape}");
  expect(dialog).toBeVisible();
  expect(vi.mocked(api).mock.calls.filter(([path]) => path.endsWith("/move"))).toHaveLength(1);
  await act(async () => {
    reject(new Error("Synthetic failure"));
  });
  expect(await within(dialog).findByRole("alert")).toHaveTextContent(t("pipeline.moveError"));
  expect(within(dialog).getByLabelText(t("pipeline.reason"))).toHaveValue("salary");
  await userEvent.click(within(dialog).getByRole("button", { name: t("common.cancel") }));
  expect(within(column("new")).getByText(card.candidate_name)).toBeVisible();
});

it("opens the email preview slot only for a non-null suggestion and makes no send request", async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("/move")
      ? {
          application: changed("screening"),
          suggested_email: { synthetic_draft: "<script>private</script>" },
        }
      : structuredClone(server),
  );
  show();
  await dragTo("screening");
  const dialog = await screen.findByRole("dialog", { name: t("pipeline.emailPreview") });
  expect(within(dialog).getByText(t("pipeline.emailPending"))).toBeVisible();
  expect(screen.queryByText("<script>private</script>")).not.toBeInTheDocument();
  expect(vi.mocked(api).mock.calls.every(([path]) => !path.includes("email"))).toBe(true);
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

it("does not move on same-column drop or cancellation", async () => {
  show();
  await dragTo("new");
  const handle = screen.getByRole("button", {
    name: t("pipeline.drag").replace("{name}", card.candidate_name),
  });
  handle.focus();
  await userEvent.keyboard("[Space][ArrowRight][Escape]");
  expect(vi.mocked(api).mock.calls.filter(([path]) => path.endsWith("/move"))).toHaveLength(0);
});

it("does not restore cached candidate data or show a toast after unmount and session cache clear", async () => {
  let resolve!: (value: MoveResult) => void;
  const pending = new Promise<MoveResult>((done) => {
    resolve = done;
  });
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith("/move") ? pending : structuredClone(server),
  );
  const client = show();
  await dragTo("screening");
  await waitFor(() =>
    expect(within(column("screening")).getByText(card.candidate_name)).toBeVisible(),
  );
  cleanup();
  client.clear();
  const success = vi.spyOn(toast, "success");
  await act(async () => {
    resolve({ application: changed("screening"), suggested_email: null });
  });
  expect(client.getQueryData(["job-pipeline", "job-fake"])).toBeUndefined();
  expect(success).not.toHaveBeenCalled();
});

it("shows loading, safe load errors with retry, and an actionable empty board", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("SYNTHETIC_PRIVATE_ERROR"));
  server = { total: 0, columns: stages.map((stage) => ({ stage, total: 0, items: [] })) };
  show();
  expect(screen.getByRole("status")).toHaveTextContent(t("common.loading"));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unknown"));
  fireEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  expect(await screen.findByText(t("pipeline.empty"))).toBeVisible();
  expect(screen.getAllByText(t("pipeline.emptyColumn"))).toHaveLength(7);
});
