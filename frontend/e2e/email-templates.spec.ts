import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("edits Vietnamese templates, inserts variables and safely previews a chosen application", async ({
  page,
  context,
}) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  const messageRequests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/email-messages")) messageRequests.push(request.method());
  });
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return ["localhost", "127.0.0.1"].includes(url.hostname) ? route.continue() : route.abort();
  });
  await page.goto("/login");
  await page
    .getByLabel(t("auth.email"), { exact: true })
    .fill("browser-email-templates@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const me = await (await context.request.get(`${base}/auth/me`)).json();
  const options = await (await context.request.get(`${base}/jobs/options`)).json();
  const jobTitle = `Email giả T22 ${Date.now()}`;
  const created = await context.request.post(`${base}/jobs`, {
    headers,
    data: {
      title: jobTitle,
      hiring_unit_id: options.hiring_units[0].id,
      owner_id: me.id,
      must_have: ["Excel"],
      status: "open",
    },
  });
  expect(created.status()).toBe(201);
  const job = await created.json();
  const buffer = readFileSync(resolve("../data/sample_cvs/cv_0044.docx"));
  const marker = Buffer.from(`t22-${job.id}`);
  const eocd = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const length = buffer.readUInt16LE(eocd + 20);
  const upload = Buffer.concat([buffer.subarray(0, eocd + 22 + length), marker]);
  upload.writeUInt16LE(length + marker.length, eocd + 20);
  const uploaded = await context.request.post(`${base}/cv-files`, {
    headers,
    multipart: {
      job_id: job.id,
      files: {
        name: "cv_0044.docx",
        mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer: upload,
      },
    },
  });
  expect(uploaded.status()).toBe(200);
  const ranking = await (await context.request.get(`${base}/jobs/${job.id}/applications`)).json();
  const application = ranking.items[0];
  expect(application).toBeDefined();
  expect((await (await context.request.get(`${base}/email-templates`)).json()).total).toBe(5);

  await page.goto("/settings");
  await page.getByRole("tab", { name: t("emailTemplates.title"), exact: true }).click();
  await page.getByRole("button", { name: t("emailTemplates.create"), exact: true }).click();
  const dialog = page.getByRole("dialog");
  const templateName = `Mẫu giả T22 ${job.id}`;
  await dialog.getByLabel(t("emailTemplates.name"), { exact: true }).fill(templateName);
  await dialog.getByLabel(t("emailTemplates.subject"), { exact: true }).fill("Thư thử vị trí ");
  await dialog
    .getByRole("button", { name: t("emailTemplates.variable.job_title"), exact: true })
    .click();
  await expect(dialog.getByLabel(t("emailTemplates.subject"), { exact: true })).toHaveValue(
    "Thư thử vị trí {{ job_title }}",
  );
  const body = dialog.getByLabel(t("emailTemplates.body"), { exact: true });
  await body.fill("<script>window.syntheticFlag=true</script>\n\nChào ");
  await dialog
    .getByRole("button", { name: t("emailTemplates.variable.candidate_name"), exact: true })
    .click();
  await expect(body).toHaveValue(
    "<script>window.syntheticFlag=true</script>\n\nChào {{ candidate_name }}",
  );
  await dialog.getByRole("button", { name: t("common.save"), exact: true }).click();
  await expect(dialog.getByText(t("emailTemplates.saved"), { exact: true })).toBeVisible();
  await dialog.getByLabel(t("emailTemplates.search"), { exact: true }).fill(jobTitle);
  await dialog.getByRole("button", { name: t("emailTemplates.find"), exact: true }).click();
  await expect(dialog.locator("option", { hasText: jobTitle })).toHaveCount(1);
  await dialog
    .getByLabel(t("emailTemplates.previewCandidate"), { exact: true })
    .selectOption(application.id);
  await dialog.getByRole("button", { name: t("emailTemplates.preview"), exact: true }).click();
  const frame = page.frameLocator(`iframe[title="${t("emailTemplates.preview")}"]`);
  await expect(frame.locator("body")).toContainText(application.candidate_name);
  await expect(frame.locator("body")).toContainText("<script>window.syntheticFlag=true</script>");
  expect(await frame.locator("script").count()).toBe(0);
  expect(await page.evaluate(() => "syntheticFlag" in window)).toBe(false);
  await body.focus();
  await body.press("Control+End");
  await dialog
    .getByRole("button", { name: t("emailTemplates.variable.interview_time"), exact: true })
    .click();
  await dialog.getByRole("button", { name: t("emailTemplates.preview"), exact: true }).click();
  await expect(dialog.getByRole("alert")).toHaveText(t("emailTemplates.missing.interview_time"));
  await page.screenshot({ path: "../var/t22-email-templates.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("button", { name: `${t("emailTemplates.edit")} ${templateName}`, exact: true })
    .click();
  await expect(body).not.toHaveValue(/interview_time/);
  const detail = await (await context.request.get(`${base}/applications/${application.id}`)).json();
  expect(detail.application.stage).toBe("new");
  expect(messageRequests).toEqual([]);
  expect(errors).toEqual([]);
});
