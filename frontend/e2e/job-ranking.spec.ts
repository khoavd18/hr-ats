import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("drops ten synthetic CVs and isolates invalid and unreadable files in a real ranked Job", async ({
  page,
  context,
}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    const host = url.protocol === "blob:" ? new URL(url.pathname).hostname : url.hostname;
    return ["localhost", "127.0.0.1"].includes(host) ? route.continue() : route.abort();
  });
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-ranking@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const api = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const me = await (await context.request.get(`${api}/auth/me`)).json();
  const unitResponse = await context.request.post(`${api}/hiring-units`, {
    headers,
    data: { name: "Đơn vị giả T14", kind: "department" },
  });
  expect(unitResponse.status()).toBe(201);
  const unit = await unitResponse.json();
  const samples = resolve("../data/sample_cvs");
  const sampleJob = JSON.parse(readFileSync(resolve(samples, "jobs.json"), "utf8")).jobs[0];
  const values = { ...sampleJob };
  delete values.id;
  const created = await context.request.post(`${api}/jobs`, {
    headers,
    data: { ...values, hiring_unit_id: unit.id, owner_id: me.id, status: "open" },
  });
  expect(created.status()).toBe(201);
  const job = await created.json();
  await page.goto("/jobs");
  await page.getByRole("link", { name: job.title, exact: true }).click();
  await expect(page).toHaveURL(`/jobs/${job.id}`);
  await expect(page.getByRole("tab")).toHaveCount(3);
  await expect(page.getByText(t("ranking.empty"), { exact: true })).toBeVisible();

  const ids = [17, 27, 32, 53, 1, 2, 3, 4, 5, 7];
  const files = ids.map((id) => {
    const label = JSON.parse(
      readFileSync(resolve(samples, `cv_${String(id).padStart(4, "0")}.json`), "utf8"),
    );
    return {
      name: label.file_name as string,
      base64: readFileSync(resolve(samples, label.file_name)).toString("base64"),
    };
  });
  files.splice(2, 0, {
    name: "invalid.exe",
    base64: Buffer.from("MZ synthetic executable").toString("base64"),
  });
  files.splice(6, 0, {
    name: "broken.pdf",
    base64: Buffer.from("%PDF-1.7\nsynthetic broken document").toString("base64"),
  });
  const transfer = await page.evaluateHandle((items) => {
    const data = new DataTransfer();
    for (const item of items) {
      const bytes = Uint8Array.from(atob(item.base64), (char) => char.charCodeAt(0));
      data.items.add(new File([bytes], item.name));
    }
    return data;
  }, files);
  await page
    .getByText(t("upload.drop"), { exact: true })
    .locator("..")
    .dispatchEvent("drop", { dataTransfer: transfer });
  const progress = page.getByRole("list", { name: t("upload.progress") });
  await expect(progress.getByRole("listitem")).toHaveCount(12);
  await expect(progress.getByText(t("upload.done"), { exact: true })).toHaveCount(10, {
    timeout: 30000,
  });
  await expect(
    progress.getByRole("listitem").filter({ hasText: "invalid.exe" }).getByRole("alert"),
  ).toHaveText(t("upload.invalidType"));
  await expect(
    progress.getByRole("listitem").filter({ hasText: "broken.pdf" }).getByRole("alert"),
  ).toHaveText(t("upload.readFailed"));
  const table = page.getByRole("table");
  await expect(table.getByRole("row")).toHaveCount(11);
  await expect(table.getByRole("columnheader")).toHaveCount(6);
  const levels = await table
    .locator("tbody tr")
    .evaluateAll((rows) => rows.map((row) => row.querySelectorAll("td")[1].textContent));
  expect(levels).toEqual([
    ...Array(3).fill(t("ai.high")),
    t("ai.medium"),
    ...Array(6).fill(t("ai.low")),
  ]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../var/t14-ranking.png", fullPage: true });
  const first = table.locator("tbody tr").first().getByRole("button");
  await first.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(first).toBeFocused();
  await page.getByLabel(t("ranking.level")).selectOption("high");
  await expect(table.locator("tbody tr")).toHaveCount(3);
  await page.getByLabel(t("ranking.stage")).selectOption("interview");
  await expect(page.getByText(t("ranking.noMatches"), { exact: true })).toBeVisible();
  await page.goto("/jobs");
  await expect(page.getByRole("columnheader")).toHaveCount(7);
  const jobRow = page
    .getByRole("row")
    .filter({ has: page.getByRole("link", { name: job.title, exact: true }) });
  await expect(jobRow).toContainText(t("ai.high"));
  expect(errors).toEqual([]);
});
