import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { t } from "../src/i18n/vi";

async function drag(page: Page, handle: Locator, destination: Locator) {
  await handle.scrollIntoViewIfNeeded();
  const start = (await handle.boundingBox())!;
  const target = (await destination.boundingBox())!;
  await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(start.x + start.width / 2 + 8, start.y + start.height / 2, { steps: 3 });
  await page.mouse.move(target.x + target.width / 2, target.y + 90, { steps: 12 });
  await page.mouse.up();
}

test("email preview is inert until Gửi, sends an interview invite, and explains missing email", async ({
  page,
  context,
}) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    const host = url.protocol === "blob:" ? new URL(url.pathname).hostname : url.hostname;
    return ["localhost", "127.0.0.1"].includes(host) ? route.continue() : route.abort();
  });
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-email@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const me = await (await context.request.get(`${base}/auth/me`)).json();
  const options = await (await context.request.get(`${base}/jobs/options`)).json();
  const result = await context.request.post(`${base}/jobs`, {
    headers,
    data: {
      title: `Email giả T23 ${Date.now()}`,
      hiring_unit_id: options.hiring_units[0].id,
      owner_id: me.id,
      must_have: ["Excel"],
      status: "open",
    },
  });
  expect(result.status()).toBe(201);
  const job = await result.json();
  const sample = JSON.parse(readFileSync(resolve("../data/sample_cvs/cv_0045.json"), "utf8"));
  const original = readFileSync(resolve("../data/sample_cvs", sample.file_name));
  const marker = Buffer.from(`t23-${job.id}`);
  const eocd = original.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const upload = Buffer.concat([original, marker]);
  upload.writeUInt16LE(original.readUInt16LE(eocd + 20) + marker.length, eocd + 20);
  const uploaded = await context.request.post(`${base}/cv-files`, {
    headers,
    multipart: {
      job_id: job.id,
      files: {
        name: sample.file_name,
        mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer: upload,
      },
    },
  });
  expect(uploaded.status()).toBe(200);
  const ranking = await (await context.request.get(`${base}/jobs/${job.id}/applications`)).json();
  expect(ranking.items).toHaveLength(1);
  const application = ranking.items[0];
  async function move(id: string, stage: string) {
    const response = await context.request.post(`${base}/applications/${id}/move`, {
      headers,
      data: { to_stage: stage },
    });
    expect(response.status()).toBe(200);
  }
  async function prepare(id: string) {
    await move(id, "screening");
    await move(id, "submitted");
    const scheduled = await context.request.post(`${base}/applications/${id}/interviews`, {
      headers,
      data: {
        scheduled_at: "2026-11-15T09:30:00+07:00",
        duration_minutes: 60,
        location_or_link: "Phòng phỏng vấn giả T23",
      },
    });
    expect(scheduled.status()).toBe(201);
    expect(
      (await context.request.post(`${base}/applications/${id}/undo`, { headers })).status(),
    ).toBe(200);
  }
  const messages = async (id: string) =>
    (await context.request.get(`${base}/email-messages?application_id=${id}`)).json();
  await prepare(application.id);
  await page.goto(`/jobs/${job.id}`);
  await page.getByRole("tab", { name: t("ranking.pipeline"), exact: true }).click();
  const handle = page.getByRole("button", {
    name: t("pipeline.drag").replace("{name}", application.candidate_name),
  });
  const target = page.getByRole("region", { name: t("stage.interview"), exact: true });
  await drag(page, handle, target);
  let dialog = page.getByRole("dialog", { name: t("pipeline.emailPreview") });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(t("email.calendar"))).toBeVisible();
  expect((await messages(application.id)).total).toBe(0);
  await dialog.getByRole("button", { name: t("email.skip"), exact: true }).click();
  expect((await messages(application.id)).total).toBe(0);
  await move(application.id, "submitted");
  await page.reload();
  await page.getByRole("tab", { name: t("ranking.pipeline"), exact: true }).click();
  await drag(page, handle, target);
  dialog = page.getByRole("dialog", { name: t("pipeline.emailPreview") });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel(t("email.subject"), { exact: true }).fill("Thư mời giả HR đã duyệt");
  await page.screenshot({ path: "../var/t23-email-preview.png", fullPage: true });
  await dialog.getByRole("button", { name: t("email.send"), exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect.poll(async () => (await messages(application.id)).items[0]?.status).toBe("sent");
  const sent = (await messages(application.id)).items;
  expect(sent).toHaveLength(1);
  expect(sent[0].subject).toBe("Thư mời giả HR đã duyệt");
  await target.getByRole("button", { name: application.candidate_name, exact: true }).click();
  const profile = page.getByRole("dialog");
  await profile.getByRole("button", { name: t("email.title"), exact: true }).click();
  await expect(profile.getByText(t("email.status.sent"), { exact: true })).toBeVisible();
  await profile.getByText("Thư mời giả HR đã duyệt", { exact: true }).click();
  await expect(profile.locator("iframe[title]").last()).toHaveAttribute("sandbox", "");
  await page.screenshot({ path: "../var/t23-email-history.png", fullPage: true });
  await page.keyboard.press("Escape");

  const bank = await (
    await context.request.get(
      `${base}/candidates?q=${encodeURIComponent("Ứng viên giả thiếu email T23")}`,
    )
  ).json();
  expect(bank.items).toHaveLength(1);
  const added = await context.request.post(`${base}/applications`, {
    headers,
    data: { job_id: job.id, candidate_id: bank.items[0].id },
  });
  expect(added.status()).toBe(201);
  const missing = await added.json();
  await prepare(missing.id);
  await page.reload();
  await page.getByRole("tab", { name: t("ranking.pipeline"), exact: true }).click();
  await drag(
    page,
    page.getByRole("button", {
      name: t("pipeline.drag").replace("{name}", bank.items[0].full_name),
    }),
    target,
  );
  await expect(page.getByRole("alert").filter({ hasText: t("email.noAddress") })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect((await messages(missing.id)).total).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
