"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { ReportFunnel, DailyCVChart } from "@/components/report-charts";
import { AgreementCard, RecruiterTable, ReportMetrics } from "@/components/report-metrics";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import {
  presetDates,
  reportDate,
  reportJobs,
  reportParams,
  shiftDay,
  validPeriod,
  type Preset,
  type RecruitersReport,
  type ReportData,
  type ReportFilters,
} from "@/lib/report-types";
import { vietnamTime } from "@/lib/task-types";
import { t } from "@/i18n/vi";

export function Reports() {
  const { user } = useAuth();
  // A role/session change discards draft selections and pending exports as well as query keys.
  return user ? (
    <ReportsView
      key={`${user.id}:${user.role}`}
      userId={user.id}
      team={user.role !== "recruiter"}
    />
  ) : null;
}

function ReportsView({ userId, team }: { userId: string; team: boolean }) {
  const [filters, setFilters] = useState<ReportFilters>(() => ({
    ...presetDates("week"),
    recruiter: "",
    job: "",
    unit: "",
  }));
  const [draft, setDraft] = useState(filters);
  const [preset, setPreset] = useState<Preset>("week");
  const [invalid, setInvalid] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportRequest = useRef<AbortController | null>(null);
  const fromRef = useRef<HTMLInputElement>(null);
  const params = reportParams(filters, team ? undefined : userId);
  const unapplied = (Object.keys(filters) as (keyof ReportFilters)[]).some(
    (key) => draft[key] !== filters[key],
  );
  const rosterParams = reportParams({ ...filters, recruiter: "", job: "", unit: "" });
  const scope = [userId, team];
  const jobs = useQuery({
    queryKey: ["report-jobs", ...scope],
    queryFn: ({ signal }) => reportJobs(signal),
    retry: false,
  });
  const roster = useQuery({
    queryKey: ["report-roster", ...scope, rosterParams],
    queryFn: ({ signal }) =>
      api<RecruitersReport>(`/reports/recruiters?${rosterParams}`, { signal }),
    enabled: team,
    retry: false,
  });
  const report = useQuery({
    queryKey: ["reports", ...scope, params],
    queryFn: async ({ signal }): Promise<ReportData> => {
      const [summary, funnel, recruiters, agreement] = await Promise.all([
        api<ReportData["summary"]>(`/reports/summary?${params}`, { signal }),
        api<ReportData["funnel"]>(`/reports/funnel?${params}`, { signal }),
        api<ReportData["recruiters"]>(`/reports/recruiters?${params}`, { signal }),
        api<ReportData["agreement"]>(`/reports/ai-agreement?${params}`, { signal }),
      ]);
      return { summary, funnel, recruiters, agreement };
    },
    retry: false,
  });
  useEffect(
    () => () => {
      exportRequest.current?.abort();
    },
    [params],
  );

  const availableJobs = jobs.isError ? [] : (jobs.data ?? []);
  const units = [
    ...new Map(availableJobs.map((job) => [job.hiring_unit_id, job.hiring_unit_name])).entries(),
  ].sort((a, b) => a[1].localeCompare(b[1], "vi"));
  const selectClass = "h-10 w-full min-w-0 rounded-md border bg-background px-3 text-sm";

  async function exportExcel() {
    if (exportRequest.current || !report.data || report.isError) return;
    const controller = new AbortController();
    exportRequest.current = controller;
    setExporting(true);
    setExportError(null);
    try {
      const blob = await api<Blob>(`/reports/export.xlsx?${params}`, {
        responseType: "blob",
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `bao-cao-${filters.from}-${shiftDay(filters.through, 1)}.xlsx`;
      anchor.style.display = "none";
      document.body.append(anchor);
      try {
        anchor.click();
      } finally {
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setExportError(error instanceof ApiError ? error.message : t("ranking.exportError"));
    } finally {
      if (exportRequest.current === controller) exportRequest.current = null;
      if (!controller.signal.aborted) setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.reports")}
        description={team ? t("reports.teamScope") : t("reports.ownScope")}
        action={
          <Button
            variant="outline"
            disabled={!report.data || report.isError || report.isFetching || exporting || unapplied}
            onClick={() => void exportExcel()}
          >
            {exporting ? t("ranking.exporting") : t("ranking.export")}
          </Button>
        }
      />
      {exportError && <p role="alert">{exportError}</p>}
      <p className="rounded-lg border bg-muted/40 p-4 text-sm">{t("reports.draft")}</p>
      <form
        className="space-y-4 rounded-lg border bg-card p-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (!validPeriod(draft.from, draft.through)) {
            setInvalid(true);
            fromRef.current?.focus();
            return;
          }
          setInvalid(false);
          setExportError(null);
          setFilters({ ...draft, recruiter: team ? draft.recruiter : "" });
          if (params === reportParams(draft, team ? undefined : userId)) void report.refetch();
        }}
      >
        <fieldset disabled={exporting} className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <label className="space-y-1">
            <span>{t("reports.period")}</span>
            <select
              className={selectClass}
              value={preset}
              onChange={(event) => {
                const next = event.target.value as Preset;
                setPreset(next);
                if (next !== "custom") setDraft({ ...draft, ...presetDates(next) });
                setInvalid(false);
              }}
            >
              {(["today", "week", "month", "custom"] as const).map((key) => (
                <option key={key} value={key}>
                  {t(`reports.${key}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span>{t("reports.from")}</span>
            <Input
              ref={fromRef}
              type="date"
              value={draft.from}
              aria-invalid={invalid}
              aria-describedby={invalid ? "report-period-error" : undefined}
              onChange={(event) => {
                setPreset("custom");
                setDraft({ ...draft, from: event.target.value });
              }}
            />
          </label>
          <label className="space-y-1">
            <span>{t("reports.through")}</span>
            <Input
              type="date"
              value={draft.through}
              aria-invalid={invalid}
              aria-describedby={invalid ? "report-period-error" : undefined}
              onChange={(event) => {
                setPreset("custom");
                setDraft({ ...draft, through: event.target.value });
              }}
            />
          </label>
          {team && (
            <label className="space-y-1">
              <span>{t("reports.recruiter")}</span>
              <select
                className={selectClass}
                value={draft.recruiter}
                disabled={roster.isPending || roster.isError}
                onChange={(event) => setDraft({ ...draft, recruiter: event.target.value })}
              >
                <option value="">{t("reports.allRecruiters")}</option>
                {!roster.isError &&
                  roster.data?.items
                    .filter((item) => item.recruiter_id !== null)
                    .map((item) => (
                      <option key={item.recruiter_id} value={item.recruiter_id!}>
                        {item.recruiter_name}
                      </option>
                    ))}
              </select>
            </label>
          )}
          <label className="space-y-1">
            <span>{t("reports.unit")}</span>
            <select
              className={selectClass}
              disabled={jobs.isPending || jobs.isError}
              value={draft.unit}
              onChange={(event) => setDraft({ ...draft, unit: event.target.value, job: "" })}
            >
              <option value="">{t("reports.allUnits")}</option>
              {units.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span>{t("reports.job")}</span>
            <select
              className={selectClass}
              disabled={jobs.isPending || jobs.isError}
              value={draft.job}
              onChange={(event) => setDraft({ ...draft, job: event.target.value })}
            >
              <option value="">{t("reports.allJobs")}</option>
              {availableJobs
                .filter((job) => !draft.unit || job.hiring_unit_id === draft.unit)
                .map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
            </select>
          </label>
          <div className="flex items-end">
            <Button type="submit">{t("reports.apply")}</Button>
          </div>
        </fieldset>
        {invalid && (
          <p role="alert" id="report-period-error">
            {t("reports.invalidPeriod")}
          </p>
        )}
        <QueryFeedback
          pending={jobs.isPending || (team && roster.isPending)}
          error={jobs.error ?? (team ? roster.error : null)}
          retry={() => {
            void jobs.refetch();
            if (team) void roster.refetch();
          }}
        />
      </form>
      {unapplied && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("reports.unapplied")}
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        {t("reports.appliedPeriod")
          .replace("{from}", reportDate(filters.from))
          .replace("{through}", reportDate(filters.through))}
      </p>
      <QueryFeedback
        pending={report.isPending}
        error={report.error}
        retry={() => {
          void report.refetch();
        }}
      />
      {report.data && !report.isError && (
        <>
          <p className="text-sm text-muted-foreground">
            {t("reports.asOf").replace("{time}", vietnamTime(report.data.summary.period.as_of))}
          </p>
          <ReportMetrics metrics={report.data.summary.metrics} />
          <div className="grid gap-6 xl:grid-cols-2">
            <ReportFunnel stages={report.data.funnel.stages} />
            <div className="min-w-0 space-y-6">
              <DailyCVChart days={report.data.summary.new_cvs_by_day} />
              <AgreementCard agreement={report.data.agreement.agreement} />
            </div>
          </div>
          <RecruiterTable items={report.data.recruiters.items} />
        </>
      )}
    </div>
  );
}
