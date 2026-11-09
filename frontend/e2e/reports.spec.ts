import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { t } from "../src/i18n/vi";
import { presetDates } from "../src/lib/report-types";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill(email);
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
}

test("reports show real scoped counts, charts and Excel for lead and recruiter at 1280px", async ({
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
  await login(page, "browser-ranking@example.invalid");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const suffix = Date.now();
  const users: { id: string; email: string; full_name: string }[] = [];
  for (const [key, role] of [
    ["lead", "lead"],
    ["a", "recruiter"],
    ["b", "recruiter"],
  ]) {
    const response = await context.request.post(`${base}/users`, {
      headers,
      data: {
        email: `report-${key}-${suffix}@example.invalid`,
        full_name: `Người giả báo cáo ${key} ${suffix}`,
        password: "synthetic-browser-password",
        role,
      },
    });
    expect(response.status()).toBe(201);
    users.push(await response.json());
  }
  const unitResponse = await context.request.post(`${base}/hiring-units`, {
    headers,
    data: { name: `Đơn vị giả báo cáo ${suffix}`, kind: "client" },
  });
  expect(unitResponse.status()).toBe(201);
  const unit = await unitResponse.json();
  const otherUnitResponse = await context.request.post(`${base}/hiring-units`, {
    headers,
    data: { name: `Đơn vị giả ngoài quyền ${suffix}`, kind: "client" },
  });
  expect(otherUnitResponse.status()).toBe(201);
  const otherUnit = await otherUnitResponse.json();
  const jobs: { id: string; title: string }[] = [];
  for (const [index, owner] of users.slice(1).entries()) {
    const created = await context.request.post(`${base}/jobs`, {
      headers,
      data: {
        title: `Việc giả báo cáo ${index} ${suffix}`,
        hiring_unit_id: unit.id,
        owner_id: owner.id,
        status: "open",
        must_have: ["Excel"],
      },
    });
    expect(created.status()).toBe(201);
    const job = await created.json();
    jobs.push(job);
    // Distinct synthetic documents exercise the real eager pipeline without external AI.
    const buffer = readFileSync(
      resolve(`../data/sample_cvs/cv_${index === 0 ? "0045" : "0046"}.docx`),
    );
    const marker = Buffer.from(`t27-${job.id}`);
    const eocd = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
    const length = buffer.readUInt16LE(eocd + 20);
    const upload = Buffer.concat([buffer.subarray(0, eocd + 22 + length), marker]);
    upload.writeUInt16LE(length + marker.length, eocd + 20);
    const uploaded = await context.request.post(`${base}/cv-files`, {
      headers,
      multipart: {
        job_id: job.id,
        files: {
          name: "cv-gia-bao-cao.docx",
          mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          buffer: upload,
        },
      },
    });
    expect(uploaded.status()).toBe(200);
  }
  const outside = await context.request.post(`${base}/jobs`, {
    headers,
    data: {
      title: `Việc giả ngoài quyền ${suffix}`,
      hiring_unit_id: otherUnit.id,
      owner_id: users[2].id,
      status: "open",
      must_have: ["Excel"],
    },
  });
  expect(outside.status()).toBe(201);

  await page.getByRole("button", { name: t("shell.logout"), exact: true }).click();
  await login(page, users[0].email);
  await page.goto("/reports");
  await expect(page.getByRole("table", { name: t("reports.recruiters") })).toBeVisible();
  await page.getByRole("combobox", { name: t("reports.unit"), exact: true }).selectOption(unit.id);
  await page.getByRole("button", { name: t("reports.apply"), exact: true }).click();
  const table = page.getByRole("table", { name: t("reports.recruiters") });
  await expect(table.getByRole("cell", { name: users[1].full_name, exact: true })).toBeVisible();
  await expect(table.getByRole("cell", { name: users[2].full_name, exact: true })).toBeVisible();
  // Upload attribution belongs to the uploader (admin), not the Application owner.
  const metrics = page.getByRole("region", { name: t("reports.metrics") });
  await expect(metrics.getByText("2", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: t("reports.daily") }).locator("svg")).toBeVisible();
  await expect(
    page.getByRole("region", { name: t("reports.funnel") }).locator("svg"),
  ).toBeVisible();
  const sortCVs = table.getByRole("button", { name: t("reports.new_cvs"), exact: true });
  await sortCVs.focus();
  await page.keyboard.press("Enter");
  await expect(
    table.getByRole("columnheader", { name: t("reports.new_cvs"), exact: true }),
  ).toHaveAttribute("aria-sort", "ascending");
  await page.keyboard.press("Enter");
  await expect(
    table.getByRole("columnheader", { name: t("reports.new_cvs"), exact: true }),
  ).toHaveAttribute("aria-sort", "descending");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: "../var/t27-reports-team.png", fullPage: true });
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: t("ranking.export"), exact: true }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toMatch(
    /^bao-cao-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.xlsx$/,
  );
  expect(
    readFileSync((await download.path())!)
      .subarray(0, 2)
      .toString(),
  ).toBe("PK");

  // A failed authorization refresh must remove the previously visible totals.
  await page.route("**/reports/summary?**", (route) =>
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "FORBIDDEN" } }),
    }),
  );
  await page.getByRole("button", { name: t("reports.apply"), exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(t("api.forbidden"));
  await expect(metrics).toHaveCount(0);
  await page.screenshot({ path: "../var/t27-reports-error.png", fullPage: true });
  await page.unroute("**/reports/summary?**");
  await page.getByRole("button", { name: t("common.retry"), exact: true }).click();
  await expect(metrics).toBeVisible();
  await page.getByRole("button", { name: t("shell.logout"), exact: true }).click();
  await login(page, users[1].email);
  await page.goto("/reports");
  await expect(table.getByRole("row")).toHaveCount(2);
  await expect(table.getByRole("cell", { name: users[1].full_name, exact: true })).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: t("reports.recruiter"), exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole("option", { name: jobs[0].title, exact: true })).toHaveCount(1);
  await expect(page.getByRole("option", { name: jobs[1].title, exact: true })).toHaveCount(0);
  await expect(page.getByRole("option", { name: otherUnit.name, exact: true })).toHaveCount(0);
  const funnel = page.getByRole("table", { name: t("reports.funnel") });
  await expect(
    funnel
      .getByRole("row")
      .filter({ hasText: t("stage.new") })
      .getByRole("cell")
      .nth(1),
  ).toHaveText("1");
  const { from, through } = presetDates("today");
  const to = new Date(`${through}T00:00:00Z`);
  to.setUTCDate(to.getUTCDate() + 1);
  const forbidden = await context.request.get(
    `${base}/reports/summary?from=${from}&to=${to.toISOString().slice(0, 10)}&recruiter_id=${users[2].id}`,
  );
  expect(forbidden.status()).toBe(403);
  await page.screenshot({ path: "../var/t27-reports-own.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(errors).toEqual([]);
});
