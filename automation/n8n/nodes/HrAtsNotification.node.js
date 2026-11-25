const { createHmac, timingSafeEqual } = require("node:crypto");

const testEvent = "integration.test";
const routes = {
  "/webhook/hr-ats/cv-scored": ["cv.scored"],
  "/webhook/hr-ats/pipeline": [
    "application.stage_changed",
    "interview.scheduled",
    "interview.cancelled",
  ],
  "/webhook/hr-ats/overdue": ["task.overdue"],
  "/webhook/hr-ats/daily-report": ["report.daily_ready"],
};
const idPattern = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const levels = { high: "Cao", medium: "Trung bình", low: "Thấp", insufficient: "Chưa đủ dữ liệu" };
const stages = {
  new: "Mới",
  screening: "Sàng lọc",
  submitted: "Đã gửi",
  interview: "Phỏng vấn",
  offer: "Đề nghị nhận việc",
  hired: "Đã nhận việc",
  rejected: "Từ chối",
  withdrawn: "Rút hồ sơ",
};
const timeInVietnam = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh",
  dateStyle: "short",
  timeStyle: "short",
});

function renderMessage(event, origin) {
  const { event_type: type, data } = event;
  if (type === testEvent && Object.keys(data).length === 0) {
    return "Thông báo thử từ HR ATS.";
  }
  if (type === "task.overdue" && Number.isSafeInteger(data.overdue_count) && data.overdue_count > 0) {
    return `Bạn có ${data.overdue_count} việc quá hạn.`;
  }
  if (type === "report.daily_ready") {
    const { report_date: day, new_cvs: cvs, interviews, placements } = data;
    if (
      typeof day !== "string" ||
      !/^\d{4}-\d{2}-\d{2}$/.test(day) ||
      ![cvs, interviews, placements].every((count) => Number.isSafeInteger(count) && count >= 0)
    ) {
      return null;
    }
    const link = new URL("/reports", origin).href;
    return [
      `Báo cáo tuyển dụng ${day.split("-").reverse().join("/")} (số liệu tham khảo)`,
      `CV mới: ${cvs}`,
      `Lịch phỏng vấn: ${interviews}`,
      `Nhận việc: ${placements}`,
      link,
    ].join("\n");
  }
  if (typeof data.application_id !== "string" || !idPattern.test(data.application_id)) {
    return null;
  }
  const link = new URL(`/applications/${data.application_id}`, origin).href;
  if (type === "cv.scored" && Object.hasOwn(levels, data.ai_level)) {
    return `Đã chấm hồ sơ. Mức AI: ${levels[data.ai_level]}.\n${link}`;
  }
  if (type === "application.stage_changed" && Object.hasOwn(stages, data.stage)) {
    return `Hồ sơ chuyển sang bước ${stages[data.stage]}.\n${link}`;
  }
  if (
    (type === "interview.scheduled" || type === "interview.cancelled") &&
    Number.isSafeInteger(data.scheduled_epoch) &&
    data.scheduled_epoch >= -62135596800 &&
    data.scheduled_epoch <= 253402300799
  ) {
    const scheduled = timeInVietnam.format(data.scheduled_epoch * 1000);
    const action = type === "interview.cancelled" ? "Đã hủy" : "Đã đặt";
    return `${action} lịch phỏng vấn lúc ${scheduled}.\n${link}`;
  }
  return null;
}

function authorizeRequest(headers, raw, path, secret, origin, now) {
  const timestamp = headers["x-hr-ats-timestamp"];
  const signature = headers["x-hr-ats-signature"];
  if (
    !Object.hasOwn(routes, path) ||
    raw.length > 16384 ||
    typeof timestamp !== "string" ||
    !/^[0-9]{1,12}$/.test(timestamp) ||
    Math.abs(now - Number(timestamp)) > 300 ||
    typeof signature !== "string" ||
    !/^v1=[a-f0-9]{64}$/.test(signature)
  ) {
    return null;
  }
  const expected = createHmac("sha256", secret).update(`${timestamp}.${path}.`).update(raw).digest();
  if (!timingSafeEqual(expected, Buffer.from(signature.slice(3), "hex"))) return null;
  let event;
  try {
    event = JSON.parse(raw.toString("utf8"));
  } catch {
    return null;
  }
  if (
    !event ||
    typeof event.event_id !== "string" ||
    !idPattern.test(event.event_id) ||
    event.version !== 1 ||
    !event.data ||
    typeof event.data !== "object" ||
    Array.isArray(event.data) ||
    (event.event_type !== testEvent && !routes[path].includes(event.event_type))
  ) {
    return null;
  }
  const message = renderMessage(event, origin);
  return message ? { event_id: event.event_id, message } : null;
}

class HrAtsNotification {
  description = {
    displayName: "Verify HR ATS Event",
    name: "hrAtsNotification",
    group: ["transform"],
    version: 1,
    description: "Authenticate an HR ATS event and format an internal notification",
    defaults: { name: "Verify HR ATS Event" },
    inputs: ["main"],
    outputs: ["main", "main"],
    outputNames: ["Valid", "Rejected"],
    credentials: [{ name: "hrAtsSigningKey", required: true }],
    properties: [
      {
        displayName: "Webhook Path",
        name: "webhookPath",
        type: "options",
        options: Object.keys(routes).map((value) => ({ name: value, value })),
        default: "/webhook/hr-ats/cv-scored",
      },
    ],
  };

  async execute() {
    const signed = [];
    const rejected = [];
    const credential = await this.getCredentials("hrAtsSigningKey");
    const origin = new URL(credential.origin);
    if (
      (origin.protocol !== "https:" &&
        !(origin.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname))) ||
      origin.username ||
      origin.password ||
      origin.href !== origin.origin + "/" ||
      Buffer.byteLength(credential.secret) < 32
    ) {
      throw new Error("Invalid HR ATS signing credential");
    }
    for (const [index, item] of this.getInputData().entries()) {
      const path = this.getNodeParameter("webhookPath", index);
      const raw = await this.helpers.getBinaryDataBuffer(index, "data");
      const event = authorizeRequest(
        item.json.headers, raw, path, credential.secret, origin, Math.floor(Date.now() / 1000),
      );
      const output = { json: event || {}, pairedItem: { item: index } };
      (event ? signed : rejected).push(output);
    }
    return [signed, rejected];
  }
}

module.exports = { HrAtsNotification, authorizeRequest };
