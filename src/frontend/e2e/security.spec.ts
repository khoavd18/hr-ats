import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("web and API return security headers and the login page runs under CSP", async ({
  page,
  context,
  request,
}) => {
  await context.route("**/*", (route) => {
    const host = new URL(route.request().url()).hostname;
    return ["localhost", "127.0.0.1"].includes(host) ? route.continue() : route.abort();
  });
  const violations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy/i.test(message.text())) violations.push(message.text());
  });
  const response = await page.goto("/login");
  expect(response).not.toBeNull();
  const headers = response!.headers();
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("no-referrer");
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["content-security-policy"]).not.toContain("unsafe-eval");
  await expect(page.getByRole("button", { name: t("auth.login"), exact: true })).toBeVisible();
  await page.getByLabel(t("auth.email"), { exact: true }).fill("headers@example.invalid");
  await expect(page.getByLabel(t("auth.email"), { exact: true })).toHaveValue(
    "headers@example.invalid",
  );
  const missing = await request.get("http://localhost:8000/api/v1/not-a-route");
  expect(missing.status()).toBe(404);
  expect(missing.headers()["content-security-policy"]).toContain("default-src 'none'");
  expect(missing.headers()["referrer-policy"]).toBe("no-referrer");
  expect(violations).toEqual([]);
});
