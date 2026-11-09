import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { t } from "../src/i18n/vi";

async function pointerDrop(page: Page, handle: Locator, destination: Locator) {
  await handle.scrollIntoViewIfNeeded();
  const start = (await handle.boundingBox())!;
  const target = (await destination.boundingBox())!;
  await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(start.x + start.width / 2 + 8, start.y + start.height / 2, { steps: 3 });
  await page.mouse.move(target.x + target.width / 2, target.y + 90, { steps: 12 });
  await page.mouse.up();
}

test("Kanban: real pointer/keyboard moves, rollback, rejection and undo at 1280px", async ({
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
  await page.getByLabel(t("auth.email"), { exact: true }).fill("dev-lead@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-dev-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const me = await (await context.request.get(`${base}/auth/me`)).json();
  const options = await (await context.request.get(`${base}/jobs/options`)).json();
  const created = await context.request.post(`${base}/jobs`, {
    headers,
    data: {
      title: `Quy trình giả T20 ${Date.now()}`,
      hiring_unit_id: options.hiring_units[0].id,
      owner_id: me.id,
      must_have: ["Excel"],
      nice_to_have: [],
      status: "open",
    },
  });
  expect(created.status()).toBe(201);
  const job = await created.json();
  await page.goto(`/jobs/${job.id}`);
  const sample = JSON.parse(readFileSync(resolve("../data/sample_cvs/cv_0043.json"), "utf8"));
  const buffer = readFileSync(resolve("../data/sample_cvs", sample.file_name));
  const marker = Buffer.from(`t20-${job.id}`);
  let upload: Buffer;
  if (sample.file_name.endsWith(".docx")) {
    const eocd = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
    const length = buffer.readUInt16LE(eocd + 20);
    upload = Buffer.concat([buffer.subarray(0, eocd + 22 + length), marker]);
    upload.writeUInt16LE(length + marker.length, eocd + 20);
  } else upload = Buffer.concat([buffer, Buffer.from(`\n% ${marker.toString("hex")}\n`)]);
  await page
    .getByLabel(t("upload.title"), { exact: true })
    .and(page.locator("input"))
    .setInputFiles({
      name: sample.file_name,
      buffer: upload,
      mimeType: sample.file_name.endsWith(".docx")
        ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        : "application/pdf",
    });
  await expect(
    page
      .getByRole("list", { name: t("upload.progress") })
      .getByText(t("upload.done"), { exact: true }),
  ).toBeVisible({ timeout: 30000 });
  const ranking = await (await context.request.get(`${base}/jobs/${job.id}/applications`)).json();
  expect(ranking.items).toHaveLength(1);
  const application = ranking.items[0];
  const handleName = t("pipeline.drag").replace("{name}", application.candidate_name);
  const handle = page.getByRole("button", { name: handleName });
  const column = (stage: "new" | "screening" | "submitted" | "rejected" | "withdrawn") =>
    page.getByRole("region", { name: t(`stage.${stage}`), exact: true });
  const candidate = (stage: "new" | "screening" | "submitted" | "rejected") =>
    column(stage).getByRole("button", { name: application.candidate_name, exact: true });
  await page.getByRole("tab", { name: t("ranking.pipeline"), exact: true }).click();
  await expect(candidate("new")).toBeVisible();
  await pointerDrop(page, handle, column("screening"));
  await expect(candidate("screening")).toBeVisible();
  await expect(page.getByRole("button", { name: t("pipeline.undo"), exact: true })).toBeVisible();
  // Switching tabs keeps the undo action attached to the same board operation.
  await page.getByRole("tab", { name: t("ranking.candidates"), exact: true }).click();
  await page.getByRole("button", { name: t("pipeline.undo"), exact: true }).click();
  await page.getByRole("tab", { name: t("ranking.pipeline"), exact: true }).click();
  await expect(candidate("new")).toBeVisible();
  await expect(page.getByText(t("pipeline.undone"), { exact: true })).toBeVisible();

  // Jumping new -> submitted is refused by the real API and rolls the card back.
  const refused = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/applications/${application.id}/move`) && response.status() === 409,
  );
  await pointerDrop(page, handle, column("submitted"));
  await refused;
  await expect(
    page.getByRole("alert").filter({ hasText: t("pipeline.invalidTransition") }),
  ).toHaveText(t("pipeline.invalidTransition"));
  await expect(candidate("new")).toBeVisible();
  await expect(candidate("submitted")).toHaveCount(0);

  // A pointer drop outside the board must not select the closest column.
  const moves: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/move")) moves.push(request.url());
  });
  const outsideStart = (await handle.boundingBox())!;
  await page.mouse.move(
    outsideStart.x + outsideStart.width / 2,
    outsideStart.y + outsideStart.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(1100, 100, { steps: 12 });
  await page.mouse.up();
  await expect(candidate("new")).toBeVisible();
  expect(moves).toHaveLength(0);

  await handle.focus();
  await page.keyboard.press("Space");
  await expect(handle).toHaveAttribute("aria-pressed", "true");
  for (const stage of [
    "screening",
    "submitted",
    "interview",
    "offer",
    "hired",
    "rejected",
  ] as const) {
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("status")).toHaveText(
      t("pipeline.over").replace("{stage}", t(`stage.${stage}`)),
    );
  }
  await page.keyboard.press("Space");
  const rejection = page.getByRole("dialog", { name: t("pipeline.rejectTitle") });
  await expect(rejection).toBeVisible();
  await expect(
    rejection.getByRole("button", { name: t("common.confirm"), exact: true }),
  ).toBeDisabled();
  await rejection.getByLabel(t("pipeline.reason")).selectOption("other");
  await page.screenshot({ path: "../var/t20-rejection.png", fullPage: true });
  await rejection.getByRole("button", { name: t("common.confirm"), exact: true }).click();
  await expect(rejection).toHaveCount(0);
  // T23 adds a separate email confirmation; declining it leaves no saved message.
  const emailPreview = page.getByRole("dialog", { name: t("pipeline.emailPreview") });
  await expect(emailPreview).toBeVisible();
  await emailPreview.getByRole("button", { name: t("email.skip"), exact: true }).click();
  const emails = await (
    await context.request.get(`${base}/email-messages?application_id=${application.id}`)
  ).json();
  expect(emails.total).toBe(0);
  await expect(candidate("rejected")).toBeVisible();
  await page.getByRole("button", { name: t("pipeline.undo"), exact: true }).click();
  await page.reload();
  await page.getByRole("tab", { name: t("ranking.pipeline"), exact: true }).click();
  await expect(candidate("new")).toBeVisible();
  await page.getByRole("button", { name: t("pipeline.more"), exact: true }).click();
  await page.getByRole("menuitemcheckbox", { name: t("stage.withdrawn"), exact: true }).click();
  await expect(column("withdrawn")).toBeAttached();
  await candidate("new").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(candidate("new")).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../var/t20-pipeline.png", fullPage: true });
  expect(errors).toEqual([]);
});
