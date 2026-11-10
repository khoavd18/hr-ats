import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";
import { presetDates, shiftDay } from "../src/lib/report-types";

test("admin records consent, renews retention, confirms erasure and inspects audit", async ({
  page,
  context,
}) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/*", (route) =>
    ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname)
      ? route.continue()
      : route.abort(),
  );
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-privacy@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const actor = await (await context.request.get(`${base}/auth/me`)).json();
  const suffix = Date.now();
  const unit = await (
    await context.request.post(`${base}/hiring-units`, {
      headers,
      data: { name: `Đơn vị giả riêng tư ${suffix}`, kind: "client" },
    })
  ).json();
  const job = await (
    await context.request.post(`${base}/jobs`, {
      headers,
      data: {
        title: `Job giả riêng tư ${suffix}`,
        hiring_unit_id: unit.id,
        owner_id: actor.id,
        status: "open",
        must_have: ["Excel"],
      },
    })
  ).json();
  const buffer = readFileSync(resolve("../data/sample_cvs/cv_0047.docx"));
  const marker = Buffer.from(`t29-${job.id}`);
  const end = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const length = buffer.readUInt16LE(end + 20);
  const upload = Buffer.concat([buffer.subarray(0, end + 22 + length), marker]);
  upload.writeUInt16LE(length + marker.length, end + 20);
  const uploaded = await context.request.post(`${base}/cv-files`, {
    headers,
    multipart: {
      job_id: job.id,
      files: {
        name: "cv-gia-rieng-tu.docx",
        mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer: upload,
      },
    },
  });
  expect(uploaded.status()).toBe(200);
  const fileId = (await uploaded.json()).items[0].cv_file.id;
  const ranking = await (await context.request.get(`${base}/jobs/${job.id}/applications`)).json();
  const application = ranking.items[0];
  expect(application).toBeDefined();
  application.candidate_name = `Ứng viên giả T29 ${suffix}`;
  expect(
    (
      await context.request.patch(`${base}/candidates/${application.candidate_id}`, {
        headers,
        data: { full_name: application.candidate_name },
      })
    ).status(),
  ).toBe(200);
  await page.goto(`/jobs/${job.id}`);
  await page
    .getByRole("table")
    .locator("tbody tr")
    .filter({ hasText: application.candidate_name })
    .getByRole("button")
    .click();
  const profile = page.getByRole("dialog");
  await expect(profile.getByText(t("profile.noConsent"))).toBeVisible();
  await profile.getByRole("button", { name: t("privacy.recordConsent"), exact: true }).click();
  const consent = page.getByRole("dialog", { name: t("privacy.recordConsent"), exact: true });
  const previous = new Date(Date.now() - 120000 + 7 * 3600000).toISOString().slice(0, 16);
  await consent.getByLabel(t("privacy.consentAt")).fill(previous);
  await consent.getByLabel(t("privacy.evidence")).fill("Bằng chứng giả T29 tại hồ sơ kiểm thử");
  await consent.getByRole("button", { name: t("common.confirm"), exact: true }).click();
  await expect(consent).not.toBeVisible();
  await expect(profile.getByText(t("profile.noConsent"))).toHaveCount(0);
  await page.goto("/settings");
  await page.getByRole("tab", { name: t("privacy.title"), exact: true }).click();
  await page.getByRole("combobox", { name: t("privacy.state"), exact: true }).selectOption("all");
  await page.getByLabel(t("privacy.search"), { exact: true }).fill(application.candidate_name);
  await page.getByRole("button", { name: t("privacy.searchButton"), exact: true }).click();
  const row = page.getByRole("row").filter({ hasText: application.candidate_name });
  await row.getByRole("button", { name: t("privacy.extend"), exact: true }).click();
  const renewal = page.getByRole("dialog", { name: t("privacy.extend"), exact: true });
  const recent = new Date(Date.now() - 60000 + 7 * 3600000).toISOString().slice(0, 16);
  await renewal.getByLabel(t("privacy.consentAt")).fill(recent);
  await renewal.getByLabel(t("privacy.evidence")).fill("Bằng chứng gia hạn giả T29");
  await renewal.getByRole("button", { name: t("common.confirm"), exact: true }).click();
  await expect(renewal).not.toBeVisible();
  await page.screenshot({ path: "../var/t29-retention.png", fullPage: true });
  const period = presetDates("today");
  const reportPath = `${base}/reports/summary?${new URLSearchParams({ from: period.from, to: shiftDay(period.through, 1), job_id: job.id })}`;
  const before = (await (await context.request.get(reportPath)).json()).metrics;
  await row.getByRole("button", { name: t("privacy.createRequest"), exact: true }).click();
  const request = page.getByRole("dialog", { name: t("privacy.createRequest"), exact: true });
  await request.getByLabel(t("privacy.requestEvidence")).fill("Yêu cầu xoá giả có xác minh T29");
  await request.getByRole("button", { name: t("privacy.createRequest"), exact: true }).click();
  await expect(request).not.toBeVisible();
  await page.getByRole("button", { name: t("privacy.execute"), exact: true }).click();
  const confirmation = page.getByRole("dialog", { name: t("privacy.executeTitle"), exact: true });
  await expect(confirmation).toContainText(application.candidate_name);
  await confirmation.getByRole("button", { name: t("common.cancel"), exact: true }).click();
  expect((await context.request.get(`${base}/cv-files/${fileId}/download`)).status()).toBe(200);
  await page.getByRole("button", { name: t("privacy.execute"), exact: true }).click();
  await confirmation.getByRole("button", { name: t("privacy.execute"), exact: true }).click();
  await expect(page.getByRole("cell", { name: t("privacy.done"), exact: true })).toBeVisible();
  expect((await context.request.get(`${base}/cv-files/${fileId}/download`)).status()).toBe(404);
  expect((await (await context.request.get(reportPath)).json()).metrics).toEqual(before);
  await page.getByRole("tab", { name: t("privacy.audit"), exact: true }).click();
  await page
    .getByRole("combobox", { name: t("privacy.action"), exact: true })
    .selectOption("candidate.purge");
  await expect(
    page.getByRole("cell", { name: t("privacy.action.purge"), exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "../var/t29-audit.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(errors).toEqual([]);
});
