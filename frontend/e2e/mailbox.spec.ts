import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("shows mailbox state and a Job's email intake code in Vietnamese", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/*", (route) =>
    ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname)
      ? route.continue()
      : route.abort(),
  );
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-mailbox@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  await page.goto("/settings");
  await page.getByRole("tab", { name: t("mailbox.title"), exact: true }).click();
  await expect(page.getByText(t("mailbox.disabled"), { exact: true })).toBeVisible();
  await expect(page.getByText(t("mailbox.lastRead"), { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await page.screenshot({ path: "../var/t24-mailbox.png", fullPage: true });
  const jobs = await (await context.request.get("http://localhost:8000/api/v1/jobs")).json();
  const job = jobs.items[0];
  expect(job).toBeDefined();
  await page.goto(`/jobs/${job.id}`);
  await expect(
    page.getByText(`[JOB-${job.id.replaceAll("-", "").slice(0, 8).toUpperCase()}]`, {
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({ path: "../var/t24-job-code.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  expect(errors).toEqual([]);
});
