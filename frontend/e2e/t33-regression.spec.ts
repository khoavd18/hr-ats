import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { t } from "../src/i18n/vi";

const api = "http://localhost:8000/api/v1";
const mailpit = process.env.T33_MAILPIT_URL ?? "http://127.0.0.1:8025";
const password = "synthetic-browser-password";
const stages = [
  "new",
  "screening",
  "submitted",
  "interview",
  "offer",
  "hired",
  "rejected",
] as const;
type Stage = (typeof stages)[number];

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill(email);
  await page.getByLabel(t("auth.password"), { exact: true }).fill(password);
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
}

function button(page: Page, name: string) {
  return page.getByRole("button", { name, exact: true });
}

test.use({ actionTimeout: 10000 });

test("T33: tuyển dụng từ cấu hình đến nhận việc, báo cáo và xoá CV", async ({
  page,
  context,
  request,
}) => {
  test.setTimeout(150000);
  await context.route("**/*", (route) =>
    ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname)
      ? route.continue()
      : route.abort(),
  );

  const tag = `T33-${Date.now()}`;
  const recruiter = `${tag.toLowerCase()}@example.invalid`;
  const unit = `Đơn vị giả ${tag}`;
  const title = `Kế toán giả ${tag}`;
  const submitSubject = `Hồ sơ giả gửi đơn vị ${tag}`;
  const interviewSubject = `Phỏng vấn giả ${tag}`;
  const rejectSubject = `Từ chối giả ${tag}`;
  const unitEmail = "t33-unit@example.invalid";

  await login(page, "browser-t33@example.invalid");
  await page.goto("/settings");
  await button(page, t("users.create")).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(t("users.fullName")).fill(`Người tuyển giả ${tag}`);
  await dialog.getByLabel(t("auth.email"), { exact: true }).fill(recruiter);
  await dialog.getByLabel(t("auth.password"), { exact: true }).fill(password);
  const createdUser = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/users") && response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: t("users.create"), exact: true }).click();
  const user = await createdUser;
  expect(user.status()).toBe(201);
  expect(await user.json()).toMatchObject({ email: recruiter, role: "recruiter" });
  await expect(dialog).not.toBeVisible();

  await page.getByRole("tab", { name: t("units.title"), exact: true }).click();
  await button(page, t("units.create")).click();
  await dialog.getByLabel(t("units.name"), { exact: true }).fill(unit);
  await dialog.getByLabel(t("units.kind"), { exact: true }).selectOption("client");
  await dialog.getByLabel(t("units.contact_email"), { exact: true }).fill(unitEmail);
  await dialog.getByRole("button", { name: t("common.save"), exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: unit })).toBeVisible();

  await page.getByRole("tab", { name: t("emailTemplates.title"), exact: true }).click();
  await button(page, t("emailTemplates.create")).click();
  const template = `Mẫu giả ${tag}`;
  await dialog.getByLabel(t("emailTemplates.name"), { exact: true }).fill(template);
  await dialog
    .getByLabel(t("emailTemplates.subject"), { exact: true })
    .fill("Hồ sơ {{ job_title }}");
  await dialog
    .getByLabel(t("emailTemplates.body"), { exact: true })
    .fill("Chào {{ candidate_name }}");
  await dialog.getByRole("button", { name: t("common.save"), exact: true }).click();
  await expect(dialog.getByText(t("emailTemplates.saved"), { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await button(page, t("shell.logout")).click();

  await login(page, recruiter);
  await page.goto("/jobs/new");
  await page.getByLabel(t("jobs.title"), { exact: true }).fill(title);
  await page.getByLabel(t("jobs.unit"), { exact: true }).selectOption({ label: unit });
  await page.getByLabel(t("jobs.must_have"), { exact: true }).fill("bookkeeping");
  await page.getByLabel(t("jobs.status"), { exact: true }).selectOption("open");
  await button(page, t("jobs.save")).click();
  await expect(page).toHaveURL("/jobs");
  await page.getByRole("link", { name: title, exact: true }).click();
  await expect(page).toHaveURL(/\/jobs\/[\w-]+$/);
  const jobId = page.url().split("/").at(-1)!;

  const files = ["cv_0049.pdf", "cv_0033.docx"].map((name) => {
    const data = readFileSync(resolve(`../data/sample_cvs/${name}`));
    if (name.endsWith(".pdf")) {
      return {
        name,
        mimeType: "application/pdf",
        buffer: Buffer.concat([data, Buffer.from(`\n% ${tag}\n`)]),
      };
    }
    const end = data.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
    expect(end).toBeGreaterThanOrEqual(0);
    const marker = Buffer.from(tag);
    const length = data.readUInt16LE(end + 20);
    const buffer = Buffer.concat([data.subarray(0, end + 22 + length), marker]);
    buffer.writeUInt16LE(length + marker.length, end + 20);
    return {
      name,
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer,
    };
  });
  await page
    .getByLabel(t("upload.title"), { exact: true })
    .and(page.locator("input"))
    .setInputFiles(files);
  const progress = page.getByRole("list", { name: t("upload.progress") });
  await expect(progress.getByText(t("upload.done"), { exact: true })).toHaveCount(2, {
    timeout: 45000,
  });

  const list = await context.request.get(`${api}/jobs/${jobId}/applications`);
  expect(list.ok()).toBe(true);
  const { items } = await list.json();
  expect(items.map((item: { ai_level: string }) => item.ai_level)).toEqual(["high", "low"]);
  const hired = items[0];
  const rejected = items[1];
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  for (const [candidate, label] of [
    [hired, "Nhận việc"],
    [rejected, "Sàng lọc"],
  ] as const) {
    candidate.candidate_name = `Ứng viên giả ${label} ${tag}`;
    const named = await context.request.patch(`${api}/candidates/${candidate.candidate_id}`, {
      headers: { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" },
      data: { full_name: candidate.candidate_name },
    });
    expect(named.ok()).toBe(true);
  }
  await page.reload();
  const rows = page.getByRole("table").locator("tbody tr");
  await expect(rows.first()).toContainText(t("ai.high"));
  await expect(rows.last()).toContainText(t("ai.low"));
  await rows.first().getByRole("button").click();
  await dialog.getByRole("button", { name: t("profile.disagree"), exact: true }).click();
  await dialog.getByLabel(t("profile.corrected")).selectOption("medium");
  await dialog.getByRole("button", { name: t("profile.sendFeedback") }).click();
  await expect(dialog.getByText(t("profile.feedbackSaved"), { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");

  const board = page.getByRole("tab", { name: t("ranking.pipeline"), exact: true });
  const column = (stage: Stage) =>
    page.getByRole("region", { name: t(`stage.${stage}`), exact: true });
  const card = (stage: Stage, name: string) =>
    column(stage).getByRole("button", { name, exact: true });
  async function move(name: string, from: Stage, to: Stage) {
    const handle = column(from).getByRole("button", {
      name: t("pipeline.drag").replace("{name}", name),
      exact: true,
    });
    if (stages.indexOf(to) - stages.indexOf(from) === 1) {
      await column(to).scrollIntoViewIfNeeded();
      await handle.scrollIntoViewIfNeeded();
      const start = (await handle.boundingBox())!;
      const end = (await column(to).boundingBox())!;
      await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
      await page.mouse.down();
      await page.mouse.move(start.x + start.width / 2 + 10, start.y + start.height / 2, {
        steps: 3,
      });
      await page.mouse.move(end.x + end.width / 2, end.y + 85, { steps: 12 });
      await page.mouse.up();
      return;
    }
    await handle.focus();
    await page.keyboard.press("Space");
    await expect(handle).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("status")).toHaveText(
      t("pipeline.over").replace("{stage}", t("stage.new")),
    );
    for (const stage of stages.slice(stages.indexOf(from) + 1, stages.indexOf(to) + 1)) {
      await page.keyboard.press("ArrowRight");
      await expect(page.getByRole("status")).toHaveText(
        t("pipeline.over").replace("{stage}", t(`stage.${stage}`)),
      );
    }
    await page.keyboard.press("Space");
  }

  async function confirmEmail(subject: string, recipient: string, attachment = false) {
    const preview = page.getByRole("dialog", { name: t("pipeline.emailPreview") });
    await expect(preview).toBeVisible();
    await preview.getByLabel(t("email.subject"), { exact: true }).fill(subject);
    await preview.getByRole("button", { name: t("email.send"), exact: true }).click();
    await expect(preview).not.toBeVisible();

    const query = new URLSearchParams({ query: `subject:${subject.split(" ").at(-1)}` });
    const find = async () => {
      const response = await request.get(`${mailpit}/api/v1/search?${query}`);
      expect(response.ok()).toBe(true);
      const { messages } = await response.json();
      return (messages ?? []).filter((message: { Subject: string }) => message.Subject === subject);
    };
    await expect.poll(async () => (await find()).length, { timeout: 15000 }).toBe(1);
    const [message] = await find();
    expect(message.To.map((to: { Address: string }) => to.Address)).toEqual([recipient]);
    if (attachment) {
      const raw = await request.get(`${mailpit}/api/v1/message/${message.ID}/raw`);
      expect(raw.ok()).toBe(true);
      expect(await raw.text()).toMatch(/Content-Type: text\/calendar/i);
    }
  }

  await board.click();
  await move(hired.candidate_name, "new", "screening");
  await expect(card("screening", hired.candidate_name)).toBeVisible();
  await button(page, t("pipeline.undo")).click();
  await expect(card("new", hired.candidate_name)).toBeVisible();
  await move(hired.candidate_name, "new", "screening");
  await move(hired.candidate_name, "screening", "submitted");
  await confirmEmail(submitSubject, unitEmail);

  await card("submitted", hired.candidate_name).click();
  const recruitment = dialog.getByRole("region", { name: t("recruitment.title"), exact: true });
  const schedule = recruitment.getByRole("form", { name: t("recruitment.schedule"), exact: true });
  const vietnamTime = (days: number) =>
    new Date(Date.now() + (days * 24 + 7) * 3600000).toISOString();
  await schedule.getByLabel(t("recruitment.scheduledAt")).fill(vietnamTime(-2).slice(0, 16));
  await schedule.getByLabel(t("recruitment.location")).fill("Phòng phỏng vấn giả");
  await schedule.getByRole("button", { name: t("recruitment.schedule"), exact: true }).click();
  const result = recruitment.getByRole("form", {
    name: `${t("recruitment.resultForm")} 1`,
    exact: true,
  });
  await expect(result).toBeVisible();
  await recruitment.getByRole("button", { name: t("pipeline.undo"), exact: true }).click();
  await expect(
    recruitment.getByRole("button", { name: t("pipeline.undo"), exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await move(hired.candidate_name, "submitted", "interview");
  await confirmEmail(interviewSubject, "cv_0049@example.com", true);

  await page.goto("/tasks");
  const followupTitle = "Cập nhật kết quả phỏng vấn";
  const followup = page.getByRole("checkbox", {
    name: t("tasks.complete").replace("{title}", followupTitle),
    exact: true,
  });
  await expect(followup).toHaveCount(0);
  expect((await request.post("http://localhost:8000/__e2e__/follow-up")).status()).toBe(204);
  await page.reload();
  await expect(followup).toBeVisible();
  await followup.check();
  await expect(followup).toHaveCount(0);
  const completed = await (await context.request.get(`${api}/tasks?status=done`)).json();
  expect(completed.items).toEqual([
    expect.objectContaining({
      title: followupTitle,
      application_id: hired.id,
      completed_at: expect.any(String),
    }),
  ]);

  await page.goto(`/jobs/${jobId}`);
  await board.click();
  await card("interview", hired.candidate_name).click();
  await result.getByLabel(t("recruitment.result")).selectOption("pass");
  const saveResult = page.waitForResponse(
    (response) =>
      response.url().includes("/interviews/") && response.request().method() === "PATCH",
  );
  await result.getByRole("button", { name: t("recruitment.saveResult") }).click();
  expect((await saveResult).ok()).toBe(true);
  const offer = recruitment.getByRole("form", { name: t("recruitment.createOffer"), exact: true });
  await offer.getByLabel(t("recruitment.salary")).fill("20000000");
  await offer.getByLabel(t("recruitment.startDate")).fill(vietnamTime(7).slice(0, 10));
  await offer.getByLabel(t("recruitment.offerStatus")).selectOption("sent");
  await offer.getByRole("button", { name: t("recruitment.createOffer"), exact: true }).click();
  const editOffer = recruitment.getByRole("form", {
    name: t("recruitment.editOffer"),
    exact: true,
  });
  await expect(editOffer).toBeVisible();
  await editOffer.getByLabel(t("recruitment.offerStatus")).selectOption("accepted");
  const savedOffer = page.waitForResponse(
    (response) => response.url().includes("/offers/") && response.request().method() === "PATCH",
  );
  await editOffer.getByRole("button", { name: t("recruitment.saveOffer") }).click();
  expect((await savedOffer).ok()).toBe(true);
  await page.keyboard.press("Escape");
  await card("offer", hired.candidate_name).click();
  const placement = recruitment.getByRole("form", {
    name: t("recruitment.placement"),
    exact: true,
  });
  await placement.getByLabel(t("recruitment.startDate")).fill(vietnamTime(7).slice(0, 10));
  await placement.getByRole("button", { name: t("recruitment.placement"), exact: true }).click();
  await expect(
    placement.getByRole("button", { name: t("recruitment.savePlacement") }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(card("hired", hired.candidate_name)).toBeVisible();

  await move(rejected.candidate_name, "new", "rejected");
  const reason = page.getByRole("dialog", { name: t("pipeline.rejectTitle") });
  await reason.getByLabel(t("pipeline.reason")).selectOption("skills");
  await reason.getByRole("button", { name: t("common.confirm"), exact: true }).click();
  await confirmEmail(rejectSubject, "cv_0033@example.com");
  await expect(card("rejected", rejected.candidate_name)).toBeVisible();

  await page.goto("/reports");
  await page.getByRole("combobox", { name: t("reports.job"), exact: true }).selectOption(jobId);
  const report = page.waitForResponse(
    (response) => response.url().includes("/reports/summary?") && response.url().includes(jobId),
  );
  await button(page, t("reports.apply")).click();
  const response = await report;
  expect(response.ok()).toBe(true);
  expect((await response.json()).metrics).toMatchObject({
    new_cvs: 2,
    screened: 3,
    // Undoing the appointment returns the application to submitted a second time.
    submitted: 2,
    interviews: { total: 1 },
    offers: 1,
    placements: 1,
  });
  const metrics = page.getByRole("region", { name: t("reports.metrics") });
  for (const [key, value] of [
    ["new_cvs", "2"],
    ["submitted", "2"],
    ["placements", "1"],
  ] as const) {
    await expect(
      metrics
        .getByRole("heading", { name: t(`reports.${key}`), exact: true })
        .locator("..")
        .getByText(value, { exact: true }),
    ).toBeVisible();
  }
  const funnel = page.getByRole("table", { name: t("reports.funnel") });
  for (const stage of ["hired", "rejected"] as const) {
    await expect(
      funnel
        .getByRole("row", { name: new RegExp(t(`stage.${stage}`)) })
        .getByRole("cell")
        .nth(1),
    ).toHaveText("1");
  }
  await button(page, t("shell.logout")).click();

  await login(page, "browser-t33@example.invalid");
  const findCandidate = async () => {
    await page.goto("/candidates");
    await page.getByLabel(t("bank.search"), { exact: true }).fill(rejected.candidate_name);
    const search = page.waitForResponse(
      (response) => new URL(response.url()).searchParams.get("q") === rejected.candidate_name,
    );
    await button(page, t("bank.find")).click();
    const response = await search;
    expect(response.ok()).toBe(true);
    return (await response.json()).items;
  };
  expect(await findCandidate()).toEqual([expect.objectContaining({ id: rejected.candidate_id })]);
  await page.goto("/settings");
  await page.getByRole("tab", { name: t("privacy.title"), exact: true }).click();
  await page.getByRole("combobox", { name: t("privacy.state"), exact: true }).selectOption("all");
  await page.getByLabel(t("privacy.search"), { exact: true }).fill(rejected.candidate_name);
  await button(page, t("privacy.searchButton")).click();
  await page
    .getByRole("row")
    .filter({ hasText: rejected.candidate_name })
    .getByRole("button", { name: t("privacy.createRequest"), exact: true })
    .click();
  const erasure = page.getByRole("dialog", { name: t("privacy.createRequest"), exact: true });
  await erasure.getByLabel(t("privacy.requestEvidence")).fill("Yêu cầu xoá giả T33");
  await erasure.getByRole("button", { name: t("privacy.createRequest"), exact: true }).click();
  await expect(erasure).not.toBeVisible();
  await page
    .getByRole("row")
    .filter({ hasText: rejected.candidate_name })
    .getByRole("button", { name: t("privacy.execute"), exact: true })
    .click();
  const confirm = page.getByRole("dialog", { name: t("privacy.executeTitle"), exact: true });
  await expect(confirm).toContainText(rejected.candidate_name);
  const erased = page.waitForResponse(
    (response) => response.url().includes("/data-requests/") && response.url().endsWith("/execute"),
  );
  await confirm.getByRole("button", { name: t("privacy.execute"), exact: true }).click();
  const erasureResponse = await erased;
  expect(erasureResponse.ok()).toBe(true);
  expect(await erasureResponse.json()).toMatchObject({
    candidate_id: rejected.candidate_id,
    status: "done",
  });
  await expect(confirm).not.toBeVisible();
  expect(await findCandidate()).toEqual([]);
  await expect(page.getByRole("article").filter({ hasText: rejected.candidate_name })).toHaveCount(
    0,
  );
  await button(page, t("shell.logout")).click();

  await login(page, "browser-t33-outsider@example.invalid");
  await page.goto("/jobs");
  await expect(page.getByRole("link", { name: title, exact: true })).toHaveCount(0);
  expect((await context.request.get(`${api}/jobs/${jobId}`)).status()).toBe(403);
});
