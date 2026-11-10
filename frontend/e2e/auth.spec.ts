import { expect, test, type Page } from "@playwright/test";
import { t } from "../src/i18n/vi";

test.beforeEach(async ({ context }) => {
  await context.route("**/*", (route) => {
    const host = new URL(route.request().url()).hostname;
    return ["localhost", "127.0.0.1"].includes(host) ? route.continue() : route.abort();
  });
});

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill(email);
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
}

test("admin signs in, navigates, creates a user, changes role and locks access", async ({
  page,
}) => {
  await page.goto("/jobs");
  await expect(page).toHaveURL("/login");
  await expect(page.getByRole("navigation")).toHaveCount(0);
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-admin@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-wrong-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: t("auth.invalidCredentials") }),
  ).toBeVisible();
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByLabel(t("shell.account"))).toContainText("Tài khoản giả admin");

  for (const [label, path] of [
    ["nav.jobs", "/jobs"],
    ["nav.candidates", "/candidates"],
    ["nav.tasks", "/tasks"],
    ["nav.reports", "/reports"],
    ["nav.settings", "/settings"],
  ] as const) {
    const link = page.getByRole("navigation").getByRole("link", { name: t(label), exact: true });
    await link.click();
    await expect(page).toHaveURL(path);
    await expect(link).toHaveAttribute("aria-current", "page");
  }
  await page.getByRole("button", { name: t("users.create"), exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(t("users.fullName")).fill("Tài khoản giả mới");
  await dialog.getByLabel(t("auth.email"), { exact: true }).fill("browser-created@example.invalid");
  await dialog.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await dialog.getByRole("button", { name: t("users.create"), exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const row = page.getByRole("row").filter({ hasText: "browser-created@example.invalid" });
  await expect(row).toContainText(t("users.active"));
  await row.getByRole("combobox").selectOption("lead");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: t("common.cancel") })
    .click();
  await expect(row.getByRole("combobox")).toHaveValue("recruiter");
  await row.getByRole("combobox").selectOption("lead");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: t("common.confirm") })
    .click();
  await expect(row.getByRole("combobox")).toHaveValue("lead");
  await row.getByRole("button", { name: t("users.lock"), exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: t("common.confirm") })
    .click();
  await expect(row).toContainText(t("users.inactive"));
  await row.getByRole("button", { name: t("users.unlock"), exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: t("common.confirm") })
    .click();
  await expect(row).toContainText(t("users.active"));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: "../var/t04-users.png" });
  await page.getByRole("button", { name: t("shell.logout"), exact: true }).click();
  await expect(page).toHaveURL("/login");
});

test("recruiter cannot access settings, refreshes expired access, and logs out", async ({
  page,
  context,
}) => {
  await login(page, "browser-recruiter@example.invalid");
  await expect(page.getByRole("link", { name: t("nav.settings"), exact: true })).toHaveCount(0);
  expect((await context.request.get("http://localhost:8000/api/v1/users")).status()).toBe(403);
  await page.goto("/settings");
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: t("users.title") })).toHaveCount(0);
  await context.clearCookies({ name: "access_token" });
  await page.goto("/jobs");
  await expect(page.getByRole("heading", { name: t("nav.jobs"), exact: true })).toBeVisible();
  expect(
    (await context.cookies()).some((cookie) => cookie.name === "access_token" && cookie.httpOnly),
  ).toBe(true);
  await page.getByRole("button", { name: t("shell.logout"), exact: true }).click();
  await expect(page).toHaveURL("/login");
  await page.goto("/candidates");
  await expect(page).toHaveURL("/login");
});
