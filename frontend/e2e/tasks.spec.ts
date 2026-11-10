import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("creates a linked task, completes it and uses the overview with the real API", async ({
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
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-tasks@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const me = await (await context.request.get(`${base}/auth/me`)).json();
  // Own the fixture: taking the first shared unit can change another test's report counts.
  const unitResponse = await context.request.post(`${base}/hiring-units`, {
    headers,
    data: { name: `Đơn vị giả T25 ${Date.now()}`, kind: "department" },
  });
  expect(unitResponse.status()).toBe(201);
  const unit = await unitResponse.json();
  const created = await context.request.post(`${base}/jobs`, {
    headers,
    data: {
      title: `Việc tuyển giả T25 ${Date.now()}`,
      hiring_unit_id: unit.id,
      owner_id: me.id,
      status: "open",
      must_have: ["Excel"],
    },
  });
  expect(created.status()).toBe(201);
  const job = await created.json();
  const buffer = readFileSync(resolve("../data/sample_cvs/cv_0045.docx"));
  const marker = Buffer.from(`t25-${job.id}`);
  const eocd = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const length = buffer.readUInt16LE(eocd + 20);
  const upload = Buffer.concat([buffer.subarray(0, eocd + 22 + length), marker]);
  upload.writeUInt16LE(length + marker.length, eocd + 20);
  const uploaded = await context.request.post(`${base}/cv-files`, {
    headers,
    multipart: {
      job_id: job.id,
      files: {
        name: "cv_0045.docx",
        mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer: upload,
      },
    },
  });
  expect(uploaded.status()).toBe(200);
  await expect(page.getByRole("region", { name: t("overview.interviews") })).toBeVisible();
  await page.goto("/tasks");
  await page.getByRole("button", { name: t("tasks.create"), exact: true }).click();
  const title = "Gọi trao đổi giả T25";
  await page.getByLabel(t("tasks.title"), { exact: true }).fill(title);
  await page.getByLabel(t("tasks.due"), { exact: true }).fill("2026-11-08T08:00");
  const selector = page.getByLabel(t("tasks.job"), { exact: true });
  await expect(selector.locator("option")).not.toHaveCount(1);
  const jobId = job.id;
  await selector.selectOption(jobId);
  await page.getByRole("button", { name: t("common.save"), exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const section = page.getByRole("region", { name: t("tasks.overdue") });
  await expect(section.getByText(title, { exact: true })).toBeVisible();
  await page.screenshot({ path: "../var/t25-tasks.png", fullPage: true });
  await page.reload();
  await page
    .getByRole("checkbox", { name: t("tasks.complete").replace("{title}", title), exact: true })
    .check();
  await expect(page.getByText(title, { exact: true })).toHaveCount(0);
  const tasks = await (
    await context.request.get("http://localhost:8000/api/v1/tasks?status=done")
  ).json();
  expect(
    tasks.items.some(
      (task: { title: string; completed_at: string }) => task.title === title && task.completed_at,
    ),
  ).toBe(true);
  // Open a synthetic candidate from a real Job, then create a task in its drawer.
  const apps = await (
    await context.request.get(`http://localhost:8000/api/v1/jobs/${jobId}/applications`)
  ).json();
  expect(apps.items).toHaveLength(1);
  await page.goto(`/jobs/${jobId}`);
  await page.getByRole("button", { name: apps.items[0].candidate_name, exact: true }).click();
  await page.getByRole("button", { name: t("tasks.create"), exact: true }).click();
  await page.getByLabel(t("tasks.title"), { exact: true }).fill("Nhắc hồ sơ giả T25");
  await page.getByRole("button", { name: t("common.save"), exact: true }).click();
  await expect(page.getByRole("dialog", { name: t("tasks.create"), exact: true })).toHaveCount(0);
  const active = await (await context.request.get("http://localhost:8000/api/v1/tasks")).json();
  expect(
    active.items.some(
      (task: { application_id: string }) => task.application_id === apps.items[0].id,
    ),
  ).toBe(true);
  await page.keyboard.press("Escape");
  await page.goto("/");
  await page.getByRole("button", { name: t("overview.upload"), exact: true }).click();
  await expect(page.getByLabel(t("overview.selectJob"), { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.screenshot({ path: "../var/t25-overview.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(errors).toEqual([]);
});
