import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { Toaster, toast } from "sonner";
import { ProfileRecruitment } from "@/components/profile-recruitment";
import { api, ApiError } from "@/lib/api";
import type { RecruitmentRecords } from "@/lib/recruitment-types";
import type { Stage } from "@/lib/ranking-types";
import { t } from "@/i18n/vi";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
let stage: Stage;
let records: RecruitmentRecords;
let version: number;
const timestamp = () => `2026-11-09T00:00:${String(++version).padStart(2, "0")}Z`;
function Harness() {
  const query = useQuery({
    queryKey: ["application-profile", "app"],
    queryFn: () => api<{ stage: Stage; records: RecruitmentRecords }>("/profile"),
  });
  return query.data && <ProfileRecruitment applicationId="app" {...query.data} />;
}
function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Harness />
      <Toaster />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  // Sonner uses browser pointer capture, which jsdom does not implement.
  HTMLElement.prototype.setPointerCapture ??= () => {};
  HTMLElement.prototype.releasePointerCapture ??= () => {};
  HTMLElement.prototype.hasPointerCapture ??= () => false;
  vi.mocked(api).mockReset();
  toast.dismiss();
  stage = "submitted";
  version = 0;
  records = { interviews: [], offers: [], placement: null };
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/profile") return structuredClone({ stage, records });
    if (path === "/applications/app/undo") {
      stage = "submitted";
      return { id: "app", stage };
    }
    const data = options?.body ? JSON.parse(options.body as string) : {};
    if (path === "/applications/app/interviews") {
      stage = "interview";
      const row = {
        id: "interview",
        ...data,
        result: "pending",
        feedback: null,
        updated_at: timestamp(),
      };
      records.interviews.push(row);
      return row;
    }
    if (path === "/interviews/interview") {
      records.interviews[0] = { ...records.interviews[0], ...data, updated_at: timestamp() };
      return records.interviews[0];
    }
    if (path === "/applications/app/offers") {
      if (data.status === "sent") stage = "offer";
      const row = {
        id: "offer",
        ...data,
        sent_at: data.status === "sent" ? timestamp() : null,
        updated_at: timestamp(),
      };
      records.offers.push(row);
      return row;
    }
    if (path === "/offers/offer") {
      if (data.status === "sent") stage = "offer";
      records.offers[0] = { ...records.offers[0], ...data, updated_at: timestamp() };
      return records.offers[0];
    }
    if (path === "/applications/app/placement") {
      stage = "hired";
      records.placement = { id: "placement", ...data, status: "active", updated_at: timestamp() };
      return records.placement;
    }
    if (path === "/placements/placement") {
      records.placement = { ...records.placement!, ...data, updated_at: timestamp() };
      return records.placement;
    }
    if (path === "/interviews/interview/ics")
      return new Blob(["BEGIN:VCALENDAR\r\nEND:VCALENDAR"], { type: "text/calendar" });
    throw new Error("Unexpected mocked request");
  });
});

async function schedule() {
  const user = userEvent.setup();
  const form = within(await screen.findByRole("form", { name: t("recruitment.schedule") }));
  await user.type(form.getByLabelText(t("recruitment.scheduledAt")), "2026-11-10T09:30");
  await user.type(
    form.getByLabelText(t("recruitment.location")),
    "Phòng giả <script>khong-chay()</script>",
  );
  await user.type(
    form.getByLabelText(t("recruitment.interviewers")),
    "Người phỏng vấn giả\ninterviewer@example.invalid",
  );
  await user.click(form.getByRole("button", { name: t("recruitment.schedule") }));
}

it("schedules in Vietnam time, saves result/feedback, downloads calendar and offers undo", async () => {
  show();
  await schedule();
  await screen.findByRole("form", { name: `${t("recruitment.resultForm")} 1` });
  expect(api).toHaveBeenCalledWith("/applications/app/interviews", {
    method: "POST",
    body: JSON.stringify({
      round: 1,
      scheduled_at: "2026-11-10T09:30:00+07:00",
      duration_minutes: 60,
      location_or_link: "Phòng giả <script>khong-chay()</script>",
      interviewers: ["Người phỏng vấn giả", "interviewer@example.invalid"],
    }),
  });
  expect(screen.getByText("Phòng giả <script>khong-chay()</script>")).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
  const user = userEvent.setup();
  const result = within(screen.getByRole("form", { name: `${t("recruitment.resultForm")} 1` }));
  await user.selectOptions(result.getByLabelText(t("recruitment.result")), "fail");
  await user.type(result.getByLabelText(t("recruitment.feedback")), "Nhận xét giả");
  await user.click(result.getByRole("button", { name: t("recruitment.saveResult") }));
  await waitFor(() => expect(records.interviews[0].feedback).toBe("Nhận xét giả"));
  expect(stage).toBe("interview");
  const objectUrl = vi.fn(() => "blob:calendar");
  const revoke = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: objectUrl, revokeObjectURL: revoke }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  await user.click(screen.getByRole("button", { name: t("recruitment.downloadIcs") }));
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(api).toHaveBeenCalledWith("/interviews/interview/ics", { responseType: "blob" });
  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:calendar"));
  click.mockRestore();
});

it("undo calls the pipeline API and keeps the saved interview", async () => {
  show();
  await schedule();
  const section = within(await screen.findByRole("region", { name: t("recruitment.title") }));
  const undo = await section.findByRole("button", { name: t("pipeline.undo") });
  await userEvent.click(undo);
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/applications/app/undo", { method: "POST" }),
  );
  expect(records.interviews).toHaveLength(1);
  expect(stage).toBe("submitted");
});

it("creates draft offer without email, records sent/accepted and creates or updates one placement", async () => {
  stage = "interview";
  show();
  const user = userEvent.setup();
  const createOffer = within(
    await screen.findByRole("form", { name: t("recruitment.createOffer") }),
  );
  await user.type(createOffer.getByLabelText(t("recruitment.salary")), "20000000");
  await user.click(createOffer.getByRole("button", { name: t("recruitment.createOffer") }));
  const editOffer = within(await screen.findByRole("form", { name: t("recruitment.editOffer") }));
  expect(stage).toBe("interview");
  await user.selectOptions(editOffer.getByLabelText(t("recruitment.offerStatus")), "sent");
  await user.click(editOffer.getByRole("button", { name: t("recruitment.saveOffer") }));
  await waitFor(() => expect(stage).toBe("offer"));
  const placement = within(screen.getByRole("form", { name: t("recruitment.placement") }));
  await waitFor(() => expect(placement.getByLabelText(t("recruitment.startDate"))).toBeEnabled());
  await user.type(placement.getByLabelText(t("recruitment.startDate")), "2026-12-01");
  await user.type(placement.getByLabelText(t("recruitment.fee")), "1000000");
  await user.type(placement.getByLabelText(t("recruitment.guarantee")), "2027-02-01");
  await user.click(placement.getByRole("button", { name: t("recruitment.placement") }));
  const update = await screen.findByRole("button", { name: t("recruitment.savePlacement") });
  expect(stage).toBe("hired");
  expect(screen.queryByRole("button", { name: t("recruitment.placement") })).toBeNull();
  await user.selectOptions(screen.getByLabelText(t("recruitment.placementStatus")), "completed");
  await user.click(update);
  await waitFor(() => expect(records.placement?.status).toBe("completed"));
  expect(vi.mocked(api).mock.calls.some(([path]) => path.includes("email"))).toBe(false);
});

it("keeps entered values on failure and prevents duplicate writes while saving", async () => {
  let reject: (error: unknown) => void = () => {};
  const normal = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation((path, options) =>
    path === "/applications/app/interviews"
      ? new Promise((_resolve, rejectPromise) => {
          reject = rejectPromise;
        })
      : normal(path, options),
  );
  show();
  await schedule();
  expect(screen.getByLabelText(t("recruitment.scheduledAt"))).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: t("common.processing") }));
  expect(
    vi.mocked(api).mock.calls.filter(([path]) => path === "/applications/app/interviews"),
  ).toHaveLength(1);
  reject(new ApiError(409, "INVALID_STAGE_TRANSITION", t("pipeline.invalidTransition")));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("pipeline.invalidTransition"));
  expect(screen.getByLabelText(t("recruitment.scheduledAt"))).toHaveValue("2026-11-10T09:30");
  expect(screen.getByLabelText(t("recruitment.location"))).toHaveValue(
    "Phòng giả <script>khong-chay()</script>",
  );
});

it("does not refresh caches or show success when a pending request finishes after closing", async () => {
  let resolve: (value: unknown) => void = () => {};
  const normal = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation((path, options) =>
    path === "/applications/app/interviews"
      ? new Promise((resolvePromise) => {
          resolve = resolvePromise;
        })
      : normal(path, options),
  );
  const success = vi.spyOn(toast, "success");
  const view = show();
  await schedule();
  const reads = vi.mocked(api).mock.calls.filter(([path]) => path === "/profile").length;
  view.unmount();
  resolve({ id: "interview" });
  await waitFor(() => expect(screen.queryByRole("form")).toBeNull());
  expect(vi.mocked(api).mock.calls.filter(([path]) => path === "/profile")).toHaveLength(reads);
  expect(success).not.toHaveBeenCalled();
  success.mockRestore();
});
