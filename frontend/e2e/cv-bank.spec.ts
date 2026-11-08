import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("searches the shared bank, adds several CVs to Jobs and merges duplicate applications", async ({
  page,
  context,
}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/*", (route) =>
    ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname)
      ? route.continue()
      : route.abort(),
  );
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-bank@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const actor = await (await context.request.get(`${base}/auth/me`)).json();
  const unitResponse = await context.request.post(`${base}/hiring-units`, {
    headers,
    data: { name: "Đơn vị giả T16", kind: "department" },
  });
  expect(unitResponse.status()).toBe(201);
  const unit = await unitResponse.json();
  const jobs: { id: string; title: string }[] = [];
  for (const title of ["Vị trí giả kho thứ nhất", "Vị trí giả kho thứ hai"]) {
    const response = await context.request.post(`${base}/jobs`, {
      headers,
      data: {
        title,
        hiring_unit_id: unit.id,
        owner_id: actor.id,
        must_have: ["Excel"],
        description: "Kế toán Excel",
        status: "open",
      },
    });
    expect(response.status()).toBe(201);
    jobs.push(await response.json());
  }
  const names = ["Ứng viên giả kho A", "Ứng viên giả kho B"];
  await page.goto("/candidates");
  await page.getByLabel(t("bank.search"), { exact: true }).fill("ke toan");
  await page.getByRole("button", { name: t("bank.find") }).click();
  for (const name of names)
    await expect(page.getByRole("article", { name, exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: names[0], exact: true })
      .getByText("Kế toán", { exact: true }),
  ).toBeVisible();
  await page.getByLabel(t("bank.semantic"), { exact: true }).check();
  await page.getByRole("button", { name: t("bank.find") }).click();
  for (const name of names) await page.getByLabel(t("bank.select") + name, { exact: true }).check();
  await page.getByRole("button", { name: t("bank.addToJob") }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(t("bank.chooseJob"), { exact: true }).selectOption(jobs[0].id);
  await dialog.getByRole("button", { name: t("bank.addSelected") }).click();
  for (const name of names)
    await expect(
      dialog.getByText(name + t("common.separator") + t("bank.added"), { exact: true }),
    ).toBeVisible();
  await dialog.getByRole("button", { name: t("common.close"), exact: true }).click();

  await page.goto(`/jobs/${jobs[1].id}`);
  await page.getByRole("button", { name: t("bank.fromBank") }).click();
  for (const name of names)
    await dialog.getByLabel(t("bank.select") + name, { exact: true }).check();
  expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await dialog.screenshot({ path: "../var/t16-suggestions.png" });
  await dialog.getByRole("button", { name: t("bank.addSelected") }).click();
  for (const name of names)
    await expect(
      dialog.getByText(name + t("common.separator") + t("bank.added"), { exact: true }),
    ).toBeVisible();
  await dialog.getByRole("button", { name: t("common.close"), exact: true }).click();
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(2);
  await page.getByRole("button", { name: t("bank.fromBank") }).click();
  for (const name of names)
    await expect(dialog.getByLabel(t("bank.select") + name, { exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await page.goto("/candidates");
  await page.getByLabel(t("bank.search"), { exact: true }).fill("ke toan");
  await page.getByRole("button", { name: t("bank.find") }).click();
  const source = page.getByRole("article", { name: names[0], exact: true });
  await source.getByRole("button", { name: t("bank.merge"), exact: true }).click();
  await expect(dialog.getByRole("button", { name: t("common.cancel") })).toBeFocused();
  await expect(dialog.getByLabel(t("bank.keepThis") + names[1], { exact: true })).toBeChecked();
  await dialog.screenshot({ path: "../var/t16-merge.png" });
  await dialog.getByRole("button", { name: t("bank.confirmMerge") }).click();
  await expect(dialog).toHaveCount(0);
  await expect(source).toHaveCount(0);
  await expect(page.getByRole("article", { name: names[1], exact: true })).toBeVisible();
  await page.screenshot({ path: "../var/t16-bank.png" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  for (const job of jobs) {
    const response = await context.request.get(`${base}/jobs/${job.id}/applications`);
    expect(response.status()).toBe(200);
    const ranking = await response.json();
    expect(ranking.total).toBe(1);
    expect(ranking.items[0].candidate_name).toBe(names[1]);
  }
  expect(errors).toEqual([]);
});
