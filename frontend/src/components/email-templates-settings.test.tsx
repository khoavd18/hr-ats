import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { EmailTemplatesSettings } from "@/components/email-templates-settings";
import { api, ApiError } from "@/lib/api";
import type { EmailTemplate } from "@/lib/email-types";
import { t } from "@/i18n/vi";

const state = vi.hoisted(() => ({ role: "lead" }));
vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({ user: { id: "actor", role: state.role } }),
}));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  api: vi.fn(),
}));

const row: EmailTemplate = {
  id: "template",
  key: "interview_invite",
  name: "Mẫu giả",
  stage: "interview",
  subject: "Mời phỏng vấn",
  body: "Chào bạn",
  is_active: true,
  requires_confirmation: true,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <EmailTemplatesSettings />
    </QueryClientProvider>,
  );
}
async function edit() {
  await userEvent.click(
    await screen.findByRole("button", { name: `${t("emailTemplates.edit")} ${row.name}` }),
  );
  return screen.getByRole("dialog");
}
beforeEach(() => {
  state.role = "lead";
  vi.mocked(api)
    .mockReset()
    .mockImplementation(async (path, options) => {
      if (path.includes("preview-options"))
        return {
          items: [{ id: "application", candidate_name: "Ứng viên giả", job_title: "Vị trí giả" }],
          total: 1,
        };
      if (path.endsWith("/preview"))
        return {
          subject: "Tiêu đề giả",
          body: "Nội dung giả",
          body_html: "<p>Nội dung giả &lt;script&gt;</p>",
        };
      if (options?.method) return { ...row, ...JSON.parse(String(options.body)) };
      return { items: [row], total: 1 };
    });
});

it("inserts Vietnamese variable buttons at the selected cursor and previews unsaved content safely", async () => {
  show();
  const dialog = await edit();
  const body = within(dialog).getByLabelText(t("emailTemplates.body")) as HTMLTextAreaElement;
  body.focus();
  body.setSelectionRange(5, 8);
  await userEvent.click(
    within(dialog).getByRole("button", {
      name: t("emailTemplates.variable.candidate_name"),
    }),
  );
  await waitFor(() => expect(body).toHaveFocus());
  expect(body.value).toBe("Chào {{ candidate_name }}");
  const subject = within(dialog).getByLabelText(t("emailTemplates.subject")) as HTMLInputElement;
  subject.focus();
  subject.setSelectionRange(0, subject.value.length);
  await userEvent.click(
    within(dialog).getByRole("button", {
      name: t("emailTemplates.variable.job_title"),
    }),
  );
  await waitFor(() => expect(subject).toHaveFocus());
  expect(subject.value).toBe("{{ job_title }}");
  await userEvent.selectOptions(
    within(dialog).getByLabelText(t("emailTemplates.previewCandidate")),
    "application",
  );
  await userEvent.click(within(dialog).getByRole("button", { name: t("emailTemplates.preview") }));
  expect(api).toHaveBeenCalledWith(
    "/email-templates/template/preview",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        application_id: "application",
        subject: "{{ job_title }}",
        body: "Chào {{ candidate_name }}",
      }),
    }),
  );
  const frame = await screen.findByTitle(t("emailTemplates.preview"));
  expect(frame).toHaveAttribute("sandbox", "");
  expect(frame.getAttribute("srcdoc")).toContain("default-src 'none'");
  expect(frame.getAttribute("srcdoc")).toContain("&lt;script&gt;");
  expect(document.querySelector("script")).toBeNull();
  expect(api).not.toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({ method: "PATCH" }),
  );
  await userEvent.type(body, " thêm");
  expect(screen.queryByTitle(t("emailTemplates.preview"))).not.toBeInTheDocument();
});

it("keeps focus and subsequent insertions in the field the editor switches to", async () => {
  show();
  const dialog = await edit();
  const body = within(dialog).getByLabelText(t("emailTemplates.body")) as HTMLTextAreaElement;
  const subject = within(dialog).getByLabelText(t("emailTemplates.subject")) as HTMLInputElement;
  // Reproduce CI timing: the editor switches fields before the next animation frame.
  const frames: FrameRequestCallback[] = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => frames.push(callback));
  body.focus();
  body.setSelectionRange(5, 8);
  await userEvent.click(
    within(dialog).getByRole("button", {
      name: t("emailTemplates.variable.candidate_name"),
    }),
  );
  expect(body).toHaveValue("Chào {{ candidate_name }}");
  subject.focus();
  subject.setSelectionRange(0, subject.value.length);
  act(() => {
    frames.splice(0).forEach((callback) => callback(0));
  });
  expect(subject).toHaveFocus();
  // Keyboard activation must restore the caret after React commits the new value.
  await userEvent.tab();
  expect(body).toHaveFocus();
  await userEvent.tab({ shift: true });
  subject.setSelectionRange(0, subject.value.length);
  const button = within(dialog).getByRole("button", {
    name: t("emailTemplates.variable.job_title"),
  });
  button.focus();
  await userEvent.keyboard("{Enter}");
  expect(subject).toHaveFocus();
  expect(subject).toHaveValue("{{ job_title }}");
  expect(subject.selectionStart).toBe(subject.value.length);
  expect(subject.selectionEnd).toBe(subject.value.length);
  await userEvent.keyboard("!");
  expect(subject).toHaveValue("{{ job_title }}!");
  expect(body).toHaveValue("Chào {{ candidate_name }}");
});

it("keeps missing-variable errors actionable and input intact for retry", async () => {
  let failed = false;
  const original = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path.endsWith("/preview") && !failed) {
      failed = true;
      throw new ApiError(
        422,
        "EMAIL_MISSING_INTERVIEW_TIME",
        t("emailTemplates.missing.interview_time"),
      );
    }
    return original(path, options);
  });
  show();
  const dialog = await edit();
  await userEvent.selectOptions(
    within(dialog).getByLabelText(t("emailTemplates.previewCandidate")),
    "application",
  );
  const button = within(dialog).getByRole("button", {
    name: t("emailTemplates.preview"),
  });
  await userEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    t("emailTemplates.missing.interview_time"),
  );
  expect(screen.getByLabelText(t("emailTemplates.body"))).toHaveValue(row.body);
  await userEvent.click(button);
  expect(await screen.findByTitle(t("emailTemplates.preview"))).toBeVisible();
});

it("creates, validates, saves and deactivates without deleting or sending", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: t("emailTemplates.create") }));
  await userEvent.click(screen.getByRole("button", { name: t("common.save") }));
  expect(screen.getByRole("alert")).toHaveTextContent(t("emailTemplates.required"));
  expect(screen.getByLabelText(t("emailTemplates.name"))).toHaveFocus();
  expect(screen.getByText(t("emailTemplates.saveFirst"))).toBeVisible();
  await userEvent.type(screen.getByLabelText(t("emailTemplates.name")), "Mẫu mới giả");
  await userEvent.type(screen.getByLabelText(t("emailTemplates.subject")), "Tiêu đề giả");
  await userEvent.type(screen.getByLabelText(t("emailTemplates.body")), "Nội dung giả");
  await userEvent.click(screen.getByRole("button", { name: t("common.save") }));
  expect(await screen.findByText(t("emailTemplates.saved"))).toBeVisible();
  const create = vi
    .mocked(api)
    .mock.calls.find(
      ([path, options]) => path === "/email-templates" && options?.method === "POST",
    )!;
  expect(JSON.parse(String(create[1]?.body))).toMatchObject({
    name: "Mẫu mới giả",
    subject: "Tiêu đề giả",
    body: "Nội dung giả",
    stage: null,
    is_active: true,
    key: expect.stringMatching(/^custom_[a-f0-9]{32}$/),
  });
  await userEvent.click(screen.getByLabelText(t("emailTemplates.active")));
  await userEvent.click(screen.getByRole("button", { name: t("common.save") }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      "/email-templates/template",
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining('"is_active":false'),
      }),
    ),
  );
  expect(
    vi
      .mocked(api)
      .mock.calls.every(
        ([path, options]) => !path.includes("email-messages") && options?.method !== "DELETE",
      ),
  ).toBe(true);
});

it("blocks duplicate actions while pending and ignores late responses after unmount", async () => {
  const original = vi.mocked(api).getMockImplementation()!;
  let finish!: (value: unknown) => void;
  vi.mocked(api).mockImplementation((path, options) =>
    options?.method === "PATCH"
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : original(path, options),
  );
  const view = show();
  await edit();
  await userEvent.click(screen.getByRole("button", { name: t("common.save") }));
  expect(screen.getByRole("button", { name: t("common.processing") })).toBeDisabled();
  for (const button of screen.getAllByRole("button", { name: t("common.close") })) {
    expect(button).toBeDisabled();
  }
  expect(screen.getByLabelText(t("emailTemplates.body"))).toBeDisabled();
  await userEvent.keyboard("{Escape}");
  expect(screen.getByRole("dialog")).toBeVisible();
  view.unmount();
  await act(async () => finish(row));
  expect(screen.queryByText(t("emailTemplates.saved"))).not.toBeInTheDocument();
});

it("shows empty/loading/error/retry states and hides everything for recruiters", async () => {
  state.role = "recruiter";
  const view = show();
  expect(api).not.toHaveBeenCalled();
  expect(view.container).toBeEmptyDOMElement();
  view.unmount();
  state.role = "admin";
  vi.mocked(api)
    .mockRejectedValueOnce(new ApiError(503, "SERVICE_UNAVAILABLE", t("api.unavailable")))
    .mockResolvedValue({ items: [], total: 0 });
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(t("api.unavailable"));
  await userEvent.click(screen.getByRole("button", { name: t("common.retry") }));
  expect(await screen.findByText(t("emailTemplates.empty"))).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: t("emailTemplates.create") }));
  expect(screen.getByRole("dialog")).toBeVisible();
});
