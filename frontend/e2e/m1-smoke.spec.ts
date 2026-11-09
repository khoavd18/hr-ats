import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("M1: recruiter creates a Job, drops five CVs, reviews AI and searches skills", async ({
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
  const samples = resolve("../data/sample_cvs");
  const fixture = JSON.parse(readFileSync(resolve(samples, "jobs.json"), "utf8"));
  const job = fixture.jobs.find((item: { id: string }) => item.id === "job_accounting");
  const labels = [8, 13, 19, 20, 29].map((id) =>
    JSON.parse(readFileSync(resolve(samples, `cv_${String(id).padStart(4, "0")}.json`), "utf8")),
  );

  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("dev-recruiter@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-dev-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await page.waitForURL("/");
  const actor = await (await context.request.get("http://localhost:8000/api/v1/auth/me")).json();
  expect(actor.role).toBe("recruiter");
  await page.getByRole("link", { name: t("nav.jobs"), exact: true }).click();
  await page.getByRole("link", { name: t("jobs.create"), exact: true }).click();
  // A unique title lets the same smoke journey be repeated against a dev database.
  const title = `${job.title} M1 ${Date.now()}`;
  await page.getByLabel(t("jobs.title"), { exact: true }).fill(title);
  await page
    .getByLabel(t("jobs.unit"), { exact: true })
    .selectOption({ label: "Đơn vị giả lập 1" });
  await page.getByLabel(t("jobs.descriptionLabel"), { exact: true }).fill(job.description);
  await page.getByLabel(t("jobs.must_have"), { exact: true }).fill(job.must_have.join("\n"));
  await page.getByLabel(t("jobs.nice_to_have"), { exact: true }).fill(job.nice_to_have.join("\n"));
  await page.getByLabel(t("jobs.status"), { exact: true }).selectOption("open");
  await page.getByRole("button", { name: t("jobs.save"), exact: true }).click();
  await expect(page).toHaveURL("/jobs");
  await page.getByRole("link", { name: title, exact: true }).click();
  await expect(page.getByText(t("ranking.empty"), { exact: true })).toBeVisible();

  // DOCX ZIP comments / PDF trailing comments change only the transport hash.
  // The original document content and expected labels remain unchanged on repeat runs.
  const files = labels.map((label) => {
    const data = readFileSync(resolve(samples, label.file_name));
    const marker = Buffer.from(`m1-${title}`);
    let upload: Buffer;
    if (label.file_name.endsWith(".docx")) {
      const eocd = data.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
      expect(eocd).toBeGreaterThanOrEqual(0);
      const size = data.readUInt16LE(eocd + 20);
      upload = Buffer.concat([data.subarray(0, eocd + 22 + size), marker]);
      upload.writeUInt16LE(size + marker.length, eocd + 20);
    } else upload = Buffer.concat([data, Buffer.from(`\n% ${marker.toString("hex")}\n`)]);
    return { name: label.file_name as string, base64: upload.toString("base64") };
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
  await expect(progress.getByRole("listitem")).toHaveCount(5);
  await expect(progress.getByText(t("upload.done"), { exact: true })).toHaveCount(5, {
    timeout: 60000,
  });
  const rows = page.getByRole("table").locator("tbody tr");
  await expect(rows).toHaveCount(5);
  const order = { high: 0, medium: 1, low: 2, insufficient: 3 };
  const levels = labels
    .map((label) => fixture.expected_level[label.id][job.id] as keyof typeof order)
    .sort((a, b) => order[a] - order[b]);
  expect(levels[0]).toBe("high");
  for (const [index, level] of levels.entries())
    await expect(rows.nth(index).locator("td").nth(1)).toHaveText(t(`ai.${level}`));
  await rows.first().getByRole("button").click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByRole("region", { name: t("profile.ai") })).toBeVisible();
  await drawer.getByRole("button", { name: t("profile.disagree"), exact: true }).click();
  await drawer.getByLabel(t("profile.corrected")).selectOption("medium");
  await drawer.getByRole("button", { name: t("profile.sendFeedback") }).click();
  await expect(drawer.getByText(t("profile.feedbackSaved"), { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await rows.first().getByRole("button").click();
  await expect(drawer.getByText(t("profile.yourFeedback") + t("profile.disagree"))).toBeVisible();
  await expect(drawer.getByRole("region", { name: t("profile.ai") })).toContainText(t("ai.medium"));
  await page.keyboard.press("Escape");

  const jobId = page.url().split("/").at(-1);
  // Confirm the candidate found in the bank belongs to this actual uploaded batch.
  const ranking = await (
    await context.request.get(`http://localhost:8000/api/v1/jobs/${jobId}/applications`)
  ).json();
  const candidateIds = ranking.items.map((item: { candidate_id: string }) => item.candidate_id);
  await page.getByRole("link", { name: t("nav.candidates"), exact: true }).click();
  await page.getByLabel(t("bank.search"), { exact: true }).fill("bookkeeping");
  await page.getByRole("button", { name: t("bank.find"), exact: true }).click();
  await expect(page.getByRole("article").filter({ hasText: "bookkeeping" }).first()).toBeVisible();
  const bank = await (
    await context.request.get("http://localhost:8000/api/v1/candidates?q=bookkeeping&page_size=100")
  ).json();
  expect(bank.items.some((item: { id: string }) => candidateIds.includes(item.id))).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../var/t18-m1-bank.png", fullPage: true });
  expect(errors).toEqual([]);
});
