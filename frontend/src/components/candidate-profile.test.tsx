import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { CandidateProfile } from "@/components/candidate-profile";
import { api, ApiError } from "@/lib/api";
import type { ApplicationDetail } from "@/lib/profile-types";
import { t } from "@/i18n/vi";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));
let detail: ApplicationDetail;
function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <CandidateProfile applicationId="app" />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.mocked(api).mockReset();
  detail = {
    candidate: {
      id: "candidate",
      full_name: "Ứng viên mô phỏng",
      email: null,
      phone: null,
      location: "Địa điểm giả",
      current_title: "Lập trình viên",
      years_experience: "3.50",
      skills: ["python"],
      consent_at: null,
    },
    application: {
      id: "app",
      ai_status: "done",
      ai_level: "insufficient",
      ai_score: 25,
      ai_reasons: ["Thiếu thông tin kinh nghiệm", "Cần xem trực tiếp CV"],
      ai_flags: [
        "job_hopping",
        "employment_gap",
        "missing_must_have",
        "overqualified",
        "unclear_cv",
        "PRIVATE_UNKNOWN_CODE",
      ],
      ai_criteria: (["met", "partial", "not_met", "unknown"] as const).map((result) => ({
        criterion: `Tiêu chí ${result}`,
        result,
        kind: "must",
        evidence: result === "unknown" ? null : "Bằng chứng giả",
      })),
    },
    cv_files: [
      {
        id: "docx",
        mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        status: "done",
        extracted_text: "Nội dung CV giả <script>khong-chay()</script>",
      },
    ],
    feedback: null,
    activities: [
      {
        id: "note",
        type: "note",
        actor_name: "HR mô phỏng",
        occurred_at: "2026-11-08T01:00:00Z",
        payload: { text: "Ghi chú giả <script>khong-chay()</script>" },
      },
      {
        id: "unknown",
        type: "PRIVATE_ACTIVITY",
        actor_name: null,
        occurred_at: "2026-11-08T01:00:00Z",
        payload: { private: "DO_NOT_RENDER" },
      },
    ],
  };
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/applications/app") return structuredClone(detail);
    if (path === "/applications/app/ai-feedback") {
      detail.feedback = JSON.parse(options?.body as string);
      return detail.feedback;
    }
    if (path === "/applications/app/notes") {
      detail.activities.unshift({
        id: "new-note",
        type: "note",
        actor_name: "HR mô phỏng",
        occurred_at: "2026-11-08T02:00:00Z",
        payload: JSON.parse(options?.body as string),
      });
      return detail.activities[0];
    }
    if (path === "/candidates/candidate") {
      Object.assign(detail.candidate, JSON.parse(options?.body as string));
      return detail.candidate;
    }
    if (path.endsWith("/download")) return new Blob(["synthetic-pdf"], { type: "application/pdf" });
    throw new Error("Unexpected test path");
  });
});

it("renders the full Vietnamese profile, four criterion results, translated flags and escaped text", async () => {
  show();
  await screen.findByText(t("profile.insufficient"));
  const assessment = screen.getByRole("region", { name: t("profile.ai") });
  for (const result of ["met", "partial", "not_met", "unknown"] as const)
    expect(within(assessment).getByText(t(`profile.${result}`))).toBeVisible();
  for (const flag of [
    "job_hopping",
    "employment_gap",
    "missing_must_have",
    "overqualified",
    "unclear_cv",
  ] as const)
    expect(within(assessment).getByText(t(`profile.flag.${flag}`))).toBeVisible();
  expect(screen.getByText(t("profile.noConsent"))).toBeVisible();
  expect(screen.getByText(t("profile.noEvidence"))).toBeVisible();
  expect(screen.getByText("Nội dung CV giả <script>khong-chay()</script>")).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
  expect(document.body.textContent).not.toMatch(
    /LLM|embedding|prompt|JSON|PRIVATE_UNKNOWN_CODE|PRIVATE_ACTIVITY|DO_NOT_RENDER/,
  );
  expect(api).not.toHaveBeenCalledWith(expect.stringContaining("/download"), expect.anything());
});

it("saves agree then disagree with a correction and comment, reloading saved feedback", async () => {
  show();
  await screen.findByText(t("profile.insufficient"));
  await userEvent.click(screen.getByRole("button", { name: t("profile.agree") }));
  await screen.findByText(t("profile.feedbackSaved"));
  expect(detail.feedback?.verdict).toBe("agree");
  await userEvent.click(screen.getByRole("button", { name: t("profile.disagree") }));
  await userEvent.selectOptions(screen.getByLabelText(t("profile.corrected")), "medium");
  await userEvent.type(screen.getByLabelText(t("profile.comment")), "Đã kiểm tra CV giả");
  await userEvent.click(screen.getByRole("button", { name: t("profile.sendFeedback") }));
  await waitFor(() =>
    expect(detail.feedback).toEqual({
      verdict: "disagree",
      corrected_level: "medium",
      comment: "Đã kiểm tra CV giả",
    }),
  );
  expect(await screen.findByText("Đã kiểm tra CV giả")).toBeVisible();
  expect(screen.getByText(t("ai.insufficient"))).toBeVisible();
});

it("edits candidate fields and appends notes to the history", async () => {
  show();
  await userEvent.click(await screen.findByRole("button", { name: t("profile.edit") }));
  await userEvent.clear(screen.getByLabelText(t("profile.name")));
  await userEvent.type(screen.getByLabelText(t("profile.name")), "Tên giả đã sửa");
  await userEvent.clear(screen.getByLabelText(t("profile.skills")));
  await userEvent.type(screen.getByLabelText(t("profile.skills")), "python, sql");
  await userEvent.click(screen.getByRole("button", { name: t("profile.save") }));
  expect(await screen.findByText(t("profile.saved"))).toBeVisible();
  expect(screen.getByText("Tên giả đã sửa")).toBeVisible();
  expect(detail.candidate.skills).toEqual(["python", "sql"]);
  const note = screen.getByLabelText(t("profile.note"));
  await userEvent.type(note, "Ghi chú mô phỏng mới");
  await userEvent.click(screen.getByRole("button", { name: t("profile.sendNote") }));
  await screen.findByText(t("profile.noteSaved"));
  expect(note).toHaveValue("");
  const history = screen.getByRole("region", { name: t("profile.history") });
  expect(within(history).getByText("Ghi chú mô phỏng mới")).toBeVisible();
});

it("shows safe errors on load and on mutation, retaining text for retry", async () => {
  vi.mocked(api).mockRejectedValueOnce(new ApiError(403, "FORBIDDEN", t("api.forbidden")));
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.forbidden"));
  expect(screen.queryByText("Ứng viên mô phỏng")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  await screen.findByText(t("profile.insufficient"));
  vi.mocked(api).mockRejectedValueOnce(
    new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable")),
  );
  await userEvent.type(screen.getByLabelText(t("profile.note")), "Ghi chú cần giữ");
  await userEvent.click(screen.getByRole("button", { name: t("profile.sendNote") }));
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  expect(screen.getByLabelText(t("profile.note"))).toHaveValue("Ghi chú cần giữ");
  await userEvent.click(screen.getByRole("button", { name: t("profile.sendNote") }));
  await screen.findByText(t("profile.noteSaved"));
});

it("loads authenticated PDF bytes and revokes its object URL when the drawer closes", async () => {
  const createUrl = vi.fn().mockReturnValue("blob:synthetic");
  const revokeUrl = vi.fn();
  vi.stubGlobal(
    "URL",
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: revokeUrl }),
  );
  detail.cv_files = [
    { id: "pdf", mime_type: "application/pdf", status: "done", extracted_text: null },
  ];
  const view = show();
  await screen.findByTitle(t("profile.cv"));
  expect(api).toHaveBeenCalledWith(
    "/cv-files/pdf/download",
    expect.objectContaining({ responseType: "blob" }),
  );
  expect(screen.getByTitle(t("profile.cv"))).toHaveAttribute("src", "blob:synthetic");
  expect(screen.getByRole("link", { name: t("profile.download") })).toHaveAttribute(
    "download",
    "cv-pdf.pdf",
  );
  view.unmount();
  expect(revokeUrl).toHaveBeenCalledWith("blob:synthetic");
});

it("handles no files or activities and pending or failed AI without offering feedback", async () => {
  detail.application.ai_status = "pending";
  detail.cv_files = [];
  detail.activities = [];
  show();
  expect(await screen.findByText(t("profile.noCv"))).toBeVisible();
  expect(screen.getByText(t("profile.noHistory"))).toBeVisible();
  expect(screen.getByText(t("upload.scoring"))).toBeVisible();
  expect(screen.queryByRole("button", { name: t("profile.agree") })).not.toBeInTheDocument();
});
