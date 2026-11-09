import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { t } from "../src/i18n/vi";

test("schedules an interview, records feedback and offer, then a single placement", async ({
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
  await page.goto("/login");
  await page
    .getByLabel(t("auth.email"), { exact: true })
    .fill("browser-recruitment@example.invalid");
  await page.getByLabel(t("auth.password"), { exact: true }).fill("synthetic-browser-password");
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
      title: `Nhận việc giả T21 ${Date.now()}`,
      hiring_unit_id: options.hiring_units[0].id,
      owner_id: me.id,
      must_have: ["Excel"],
      nice_to_have: [],
      status: "open",
    },
  });
  expect(created.status()).toBe(201);
  const job = await created.json();
  const buffer = readFileSync(resolve("../data/sample_cvs/cv_0044.docx"));
  const marker = Buffer.from(`t21-${job.id}`);
  const eocd = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const length = buffer.readUInt16LE(eocd + 20);
  const upload = Buffer.concat([buffer.subarray(0, eocd + 22 + length), marker]);
  upload.writeUInt16LE(length + marker.length, eocd + 20);
  const uploaded = await context.request.post(`${base}/cv-files`, {
    headers,
    multipart: {
      job_id: job.id,
      files: {
        name: "cv_0044.docx",
        mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer: upload,
      },
    },
  });
  expect(uploaded.status()).toBe(200);
  const ranking = await (await context.request.get(`${base}/jobs/${job.id}/applications`)).json();
  const application = ranking.items[0];
  expect(application).toBeDefined();
  for (const to_stage of ["screening", "submitted"]) {
    expect(
      (
        await context.request.post(`${base}/applications/${application.id}/move`, {
          headers,
          data: { to_stage },
        })
      ).status(),
    ).toBe(200);
  }
  await page.goto(`/jobs/${job.id}`);
  await page.getByRole("button", { name: application.candidate_name, exact: true }).click();
  const drawer = page.getByRole("dialog");
  const section = drawer.getByRole("region", { name: t("recruitment.title"), exact: true });
  const schedule = section.getByRole("form", { name: t("recruitment.schedule"), exact: true });
  await schedule.getByLabel(t("recruitment.scheduledAt")).fill("2026-11-10T09:30");
  await schedule.getByLabel(t("recruitment.duration")).fill("75");
  await schedule.getByLabel(t("recruitment.location")).fill("Phòng giả T21");
  await schedule.getByLabel(t("recruitment.interviewers")).fill("Người phỏng vấn giả T21");
  await schedule.getByRole("button", { name: t("recruitment.schedule"), exact: true }).click();
  const result = section.getByRole("form", {
    name: `${t("recruitment.resultForm")} 1`,
    exact: true,
  });
  await expect(result).toBeVisible();
  let detail = await (await context.request.get(`${base}/applications/${application.id}`)).json();
  expect(detail.application.stage).toBe("interview");
  expect(detail.interviews).toHaveLength(1);
  const downloadEvent = page.waitForEvent("download");
  await section.getByRole("button", { name: t("recruitment.downloadIcs") }).click();
  expect((await downloadEvent).suggestedFilename()).toBe(
    `interview-${detail.interviews[0].id}.ics`,
  );
  await section.getByRole("button", { name: t("pipeline.undo"), exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await context.request.get(`${base}/applications/${application.id}`)).json())
          .application.stage,
    )
    .toBe("submitted");
  await expect(result).toBeVisible(); // Undo retains the saved appointment.
  expect(
    (
      await context.request.post(`${base}/applications/${application.id}/move`, {
        headers,
        data: { to_stage: "interview" },
      })
    ).status(),
  ).toBe(200);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: application.candidate_name, exact: true }).click();
  await result.getByLabel(t("recruitment.result")).selectOption("pass");
  await result.getByLabel(t("recruitment.feedback")).fill("Nhận xét phỏng vấn giả T21");
  await result.getByRole("button", { name: t("recruitment.saveResult") }).click();
  await expect(result.getByLabel(t("recruitment.feedback"))).toHaveValue(
    "Nhận xét phỏng vấn giả T21",
  );
  const offer = section.getByRole("form", { name: t("recruitment.createOffer"), exact: true });
  await offer.getByLabel(t("recruitment.salary")).fill("20000000");
  await offer.getByLabel(t("recruitment.offerStatus")).selectOption("sent");
  await offer.getByRole("button", { name: t("recruitment.createOffer"), exact: true }).click();
  const editOffer = section.getByRole("form", { name: t("recruitment.editOffer"), exact: true });
  await expect(editOffer).toBeVisible();
  await editOffer.getByLabel(t("recruitment.offerStatus")).selectOption("accepted");
  await editOffer.getByRole("button", { name: t("recruitment.saveOffer") }).click();
  const placement = section.getByRole("form", { name: t("recruitment.placement"), exact: true });
  await placement.getByLabel(t("recruitment.startDate")).fill("2026-12-01");
  await placement.getByLabel(t("recruitment.fee")).fill("1000000");
  await placement.getByLabel(t("recruitment.guarantee")).fill("2027-02-01");
  await placement.getByRole("button", { name: t("recruitment.placement"), exact: true }).click();
  await expect(
    placement.getByRole("button", { name: t("recruitment.savePlacement") }),
  ).toBeVisible();
  detail = await (await context.request.get(`${base}/applications/${application.id}`)).json();
  expect(detail.application.stage).toBe("hired");
  expect(detail.placement.fee_amount).toBe(1000000);
  expect(detail.interviews[0].result).toBe("pass");
  expect(detail.offers[0].status).toBe("accepted");
  expect(
    (
      await context.request.post(`${base}/applications/${application.id}/placement`, {
        headers,
        data: { start_date: "2026-12-01" },
      })
    ).status(),
  ).toBe(409);
  await page.screenshot({ path: "../var/t21-recruitment.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press("Escape");
  await page.reload();
  await page.getByRole("button", { name: application.candidate_name, exact: true }).click();
  await expect(
    placement.getByRole("button", { name: t("recruitment.savePlacement") }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
