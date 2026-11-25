import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("quản trị bật tích hợp, gửi thử và theo dõi nhật ký", async ({ context, page }) => {
  await context.route("**/*", (route) => {
    const host = new URL(route.request().url()).hostname;
    return ["localhost", "127.0.0.1"].includes(host) ? route.continue() : route.abort();
  });
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-t38@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  await page.getByRole("link", { name: t("nav.settings"), exact: true }).click();
  await page.getByRole("tab", { name: t("integrations.title"), exact: true }).click();

  const overdue = page.getByRole("region", { name: t("integrations.kind.overdue") });
  const testOverdue = overdue.getByRole("button", { name: t("integrations.test") });
  await expect(testOverdue).toBeDisabled();
  await overdue.getByRole("button", { name: t("integrations.enable"), exact: true }).click();
  await expect(testOverdue).toBeEnabled();
  await testOverdue.click();
  const history = page.getByRole("region", { name: t("integrations.history") });
  await expect(
    history.getByRole("row").filter({ hasText: t("integrations.kind.overdue") }),
  ).toContainText(t("integrations.status.sent"));

  const pipeline = page.getByRole("region", { name: t("integrations.kind.pipeline") });
  await pipeline.getByRole("button", { name: t("integrations.enable"), exact: true }).click();
  await pipeline.getByRole("button", { name: t("integrations.test") }).click();
  const waiting = history.getByRole("row").filter({ hasText: t("integrations.kind.pipeline") });
  await expect(waiting).toContainText(t("integrations.status.retrying"));
  await expect(waiting).toContainText("WEBHOOK_DELIVERY_FAILED");
  await pipeline.getByRole("button", { name: t("integrations.disable"), exact: true }).click();
  await expect(waiting).toContainText(t("integrations.status.paused"));
  await pipeline.getByRole("button", { name: t("integrations.enable"), exact: true }).click();
  await expect(waiting).toContainText(t("integrations.status.retrying"));
  await pipeline.getByRole("button", { name: t("integrations.disable"), exact: true }).click();
  await expect(pipeline.getByRole("button", { name: t("integrations.test") })).toBeDisabled();
});
