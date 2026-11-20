import { t } from "@/i18n/vi";
import { api } from "@/lib/api";
import type { Job } from "@/lib/job-types";
import type { Stage } from "@/lib/ranking-types";
import { vietnamDay } from "@/lib/task-types";

export type Period = {
  from_date: string;
  to_date: string;
  timezone: string;
  as_of: string;
  definition_status: "draft";
  recruiter_id: string | null;
  job_id: string | null;
  hiring_unit_id: string | null;
};
export type Median = { days: number | null; sample_count: number; excluded_count: number };
export type Agreement = { agree: number; disagree: number; total: number; rate: number | null };
export type FunnelStage = {
  stage: Stage;
  count: number;
  next_stage: Stage | null;
  next_count: number | null;
  conversion_rate: number | null;
};
export const activityTypes = [
  "note",
  "call",
  "email_sent",
  "stage_changed",
  "cv_uploaded",
  "ai_scored",
  "ai_feedback",
  "interview_scheduled",
  "offer_made",
  "task_done",
] as const;
export type Metrics = {
  new_cvs: number;
  screened: number;
  submitted: number;
  interviews: { total: number; elapsed: number; upcoming: number };
  offers: number;
  placements: number;
  funnel: FunnelStage[];
  time_to_fill: Median;
  stage_duration: Record<Stage, Median>;
  overdue_jobs: number;
  placement_revenue: { amount: number | null; known_count: number; missing_count: number };
  ai_agreement: Agreement;
  activities: Record<(typeof activityTypes)[number], number>;
};
export type DailyCVs = { date: string; count: number };
export type SummaryReport = { period: Period; metrics: Metrics; new_cvs_by_day: DailyCVs[] };
export type RecruiterRow = {
  recruiter_id: string | null;
  recruiter_name: string | null;
  metrics: Metrics;
};
export type RecruitersReport = { period: Period; items: RecruiterRow[] };
export type ReportData = {
  summary: SummaryReport;
  funnel: { period: Period; stages: FunnelStage[] };
  recruiters: RecruitersReport;
  agreement: { period: Period; agreement: Agreement };
};
export type ReportFilters = {
  from: string;
  through: string;
  recruiter: string;
  job: string;
  unit: string;
};
export type Preset = "today" | "week" | "month" | "custom";

export function shiftDay(day: string, offset: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

export function presetDates(preset: Exclude<Preset, "custom">, now = new Date()) {
  const through = vietnamDay(now);
  const from =
    preset === "week"
      ? shiftDay(through, -6)
      : preset === "month"
        ? `${through.slice(0, 8)}01`
        : through;
  return { from, through };
}

export function validPeriod(from: string, through: string): boolean {
  const validDay = (day: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return false;
    const time = Date.parse(`${day}T00:00:00Z`);
    return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === day;
  };
  if (!validDay(from) || !validDay(through) || from <= "0001-01-01" || through >= "9999-12-31")
    return false;
  const days =
    (Date.parse(`${through}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000 + 1;
  return days >= 1 && days <= 366;
}

export function reportParams(filters: ReportFilters, ownId?: string): string {
  const params = new URLSearchParams({ from: filters.from, to: shiftDay(filters.through, 1) });
  if (ownId || filters.recruiter) params.set("recruiter_id", ownId || filters.recruiter);
  if (filters.job) params.set("job_id", filters.job);
  if (filters.unit) params.set("hiring_unit_id", filters.unit);
  return params.toString();
}

// Enumerate every authorized page; /jobs/options also contains unrelated units/users.
export async function reportJobs(signal: AbortSignal): Promise<Job[]> {
  const jobs: Job[] = [];
  for (let page = 1; ; page += 1) {
    signal.throwIfAborted();
    const result = await api<{ items: Job[]; total: number }>(`/jobs?page=${page}&page_size=100`, {
      signal,
    });
    jobs.push(...result.items);
    if (jobs.length >= result.total || result.items.length === 0) return jobs;
  }
}

export const reportNumber = (value: number) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value);
export const reportRate = (value: number | null) =>
  value === null
    ? t("reports.undefined")
    : new Intl.NumberFormat("vi-VN", {
        style: "percent",
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      }).format(value);
export const reportDate = (day: string) =>
  new Intl.DateTimeFormat("vi-VN", {
    timeZone: "UTC",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(`${day}T00:00:00Z`));
