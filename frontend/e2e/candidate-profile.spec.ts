import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

// Full Chromium includes the native PDF viewer used by HR's desktop browser.
test.use({ channel: "chromium" });

test("reviews original CVs, corrects a profile and saves human feedback and notes", async ({
  page,
  context,
}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    const host = url.protocol === "blob:" ? new URL(url.pathname).hostname : url.hostname;
    const nativePdfResource =
      (url.protocol === "chrome-extension:" && host === "mhjfbmdgcfjbbpaeojofohoefgiehjai") ||
      (url.protocol === "chrome:" && host === "resources");
    return ["localhost", "127.0.0.1"].includes(host) || nativePdfResource
      ? route.continue()
      : route.abort();
  });
  await page.goto("/login");
  await page.getByLabel(t("auth.email"), { exact: true }).fill("browser-profile@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
  await page.getByRole("button", { name: t("auth.login"), exact: true }).click();
  await expect(page).toHaveURL("/");
  const base = "http://localhost:8000/api/v1";
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "csrf_token")!.value;
  const headers = { "X-CSRF-Token": csrf, Origin: "http://localhost:3000" };
  const actor = await (await context.request.get(`${base}/auth/me`)).json();
  const unit = await context.request.post(`${base}/hiring-units`, {
    headers,
    data: { name: "Đơn vị giả T15", kind: "department" },
  });
  expect(unit.status()).toBe(201);
  const jobResponse = await context.request.post(`${base}/jobs`, {
    headers,
    data: {
      title: "Vị trí giả T15",
      description: "Python",
      must_have: ["Python"],
      hiring_unit_id: (await unit.json()).id,
      owner_id: actor.id,
      status: "open",
    },
  });
  expect(jobResponse.status()).toBe(201);
  const job = await jobResponse.json();
  const files: { candidate_id: string }[] = [];
  for (const name of ["cv_0031.docx", "cv_0016.pdf"]) {
    const response = await context.request.post(`${base}/cv-files`, {
      headers,
      multipart: {
        job_id: job.id,
        files: {
          name,
          mimeType: name.endsWith("pdf")
            ? "application/pdf"
            : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          buffer: readFileSync(resolve("../data/sample_cvs", name)),
        },
      },
    });
    expect(response.status()).toBe(200);
    const file = (await response.json()).items[0];
    expect(file.error).toBeNull();
    const status = await (await context.request.get(`${base}/cv-files/${file.cv_file.id}`)).json();
    expect(status.status).toBe("done");
    files.push(status);
  }
  const ranking = await (await context.request.get(`${base}/jobs/${job.id}/applications`)).json();
  const docxIndex = ranking.items.findIndex(
    (item: { candidate_id: string }) => item.candidate_id === files[0].candidate_id,
  );
  const pdfIndex = ranking.items.findIndex(
    (item: { candidate_id: string }) => item.candidate_id === files[1].candidate_id,
  );
  expect(docxIndex).toBeGreaterThanOrEqual(0);
  expect(pdfIndex).toBeGreaterThanOrEqual(0);
  await page.goto(`/jobs/${job.id}`);
  const rows = page.getByRole("table").locator("tbody tr");
  await expect(rows).toHaveCount(2);
  const trigger = rows.nth(docxIndex).getByRole("button");
  await trigger.click();
  const drawer = page.getByRole("dialog");
  await expect(
    drawer.getByRole("region", { name: t("profile.cv") }).locator("pre"),
  ).not.toBeEmpty();
  await expect(drawer.getByRole("region", { name: t("profile.ai") })).toBeVisible();
  await expect(drawer.getByRole("columnheader", { name: t("profile.evidence") })).toBeVisible();
  expect(await drawer.innerText()).not.toMatch(/\b(?:LLM|embedding|prompt|JSON)\b/i);
  await drawer.getByRole("button", { name: t("profile.agree"), exact: true }).click();
  await expect(drawer.getByText(t("profile.feedbackSaved"))).toBeVisible();
  await drawer.getByRole("button", { name: t("profile.disagree"), exact: true }).click();
  await drawer.getByLabel(t("profile.corrected")).selectOption("low");
  await drawer.getByLabel(t("profile.comment")).fill("Đánh giá thủ công trên CV giả");
  await drawer.getByRole("button", { name: t("profile.sendFeedback") }).click();
  await expect(drawer.getByText("Đánh giá thủ công trên CV giả")).toBeVisible();
  await drawer.getByLabel(t("profile.note")).fill("Ghi chú giả cho lần xem hồ sơ");
  await drawer.getByRole("button", { name: t("profile.sendNote") }).click();
  await expect(
    drawer
      .getByRole("region", { name: t("profile.history") })
      .getByText("Ghi chú giả cho lần xem hồ sơ"),
  ).toBeVisible();
  await drawer.getByRole("button", { name: t("profile.edit") }).click();
  await drawer.getByLabel(t("profile.name")).fill("Tên mô phỏng T15");
  await drawer.getByRole("button", { name: t("profile.save") }).click();
  await expect(drawer.getByText(t("profile.saved"))).toBeVisible();
  await expect(
    drawer.getByRole("region", { name: t("profile.info") }).getByText("Tên mô phỏng T15"),
  ).toBeVisible();
  await expect(drawer.getByRole("heading", { name: "Tên mô phỏng T15" })).toBeVisible();
  expect(await drawer.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await drawer.evaluate((element) => {
    element.scrollTop = 0;
  });
  await drawer.screenshot({ path: "../var/t15-profile-docx.png" });
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await trigger.click();
  await expect(drawer.getByText("Đánh giá thủ công trên CV giả")).toBeVisible();
  await page.keyboard.press("Escape");
  await rows.nth(pdfIndex).getByRole("button").click();
  const viewer = drawer.locator("iframe");
  await expect(viewer).toHaveAttribute("src", /^blob:/);
  await expect
    .poll(async () => {
      const counts = await Promise.all(
        page
          .frames()
          .map((frame) => frame.locator('embed[type="application/x-google-chrome-pdf"]').count()),
      );
      return counts.reduce((total, count) => total + count, 0);
    })
    .toBeGreaterThan(0);
  await expect(drawer.getByRole("link", { name: t("profile.download") })).toBeVisible();
  await drawer.evaluate((element) => {
    element.scrollTop = 0;
  });
  await drawer.screenshot({ path: "../var/t15-profile-pdf.png" });
  await page.keyboard.press("Escape");
  expect(errors).toEqual([]);
});
