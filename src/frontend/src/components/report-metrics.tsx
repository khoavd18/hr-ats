"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { t } from "@/i18n/vi";
import { stages } from "@/lib/ranking-types";
import {
  activityTypes,
  reportNumber,
  reportRate,
  type Agreement,
  type Metrics,
  type RecruiterRow,
} from "@/lib/report-types";

const countKeys = [
  "new_cvs",
  "screened",
  "submitted",
  "offers",
  "placements",
  "overdue_jobs",
] as const;
export function ReportMetrics({ metrics }: { metrics: Metrics }) {
  const cards: { label: string; value: string; hint: string | null }[] = countKeys.map((key) => ({
    label: t(`reports.${key}`),
    value: reportNumber(metrics[key]),
    hint: key === "overdue_jobs" ? t("reports.overdueHelp") : null,
  }));
  cards.splice(3, 0, {
    label: t("reports.interviews"),
    value: reportNumber(metrics.interviews.total),
    hint: t("reports.interviewsHelp")
      .replace("{elapsed}", reportNumber(metrics.interviews.elapsed))
      .replace("{upcoming}", reportNumber(metrics.interviews.upcoming)),
  });
  return (
    <>
      <section
        aria-label={t("reports.metrics")}
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      >
        {cards.map((card) => (
          <div key={card.label} className="rounded-lg border bg-card p-5">
            <h2 className="text-sm text-muted-foreground">{card.label}</h2>
            <p className="mt-2 text-3xl font-semibold tabular-nums">{card.value}</p>
            {card.hint && <p className="mt-2 text-sm text-muted-foreground">{card.hint}</p>}
          </div>
        ))}
        <div className="rounded-lg border bg-card p-5">
          <h2 className="text-sm text-muted-foreground">{t("reports.timeToFill")}</h2>
          <p className="mt-2 text-3xl font-semibold">
            {metrics.time_to_fill.days === null
              ? t("reports.undefined")
              : t("reports.days").replace("{count}", reportNumber(metrics.time_to_fill.days))}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("reports.samples")
              .replace("{count}", reportNumber(metrics.time_to_fill.sample_count))
              .replace("{excluded}", reportNumber(metrics.time_to_fill.excluded_count))}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-5">
          <h2 className="text-sm text-muted-foreground">{t("reports.revenue")}</h2>
          <p className="mt-2 text-3xl font-semibold">
            {metrics.placement_revenue.amount === null
              ? t("reports.undefined")
              : t("reports.vnd").replace(
                  "{amount}",
                  reportNumber(metrics.placement_revenue.amount),
                )}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("reports.feeSamples")
              .replace("{known}", reportNumber(metrics.placement_revenue.known_count))
              .replace("{missing}", reportNumber(metrics.placement_revenue.missing_count))}
          </p>
        </div>
      </section>
      <details className="rounded-lg border bg-card p-5">
        <summary className="cursor-pointer font-medium">{t("reports.moreMetrics")}</summary>
        <div className="mt-4 grid gap-6 lg:grid-cols-2">
          <Table aria-label={t("reports.durations")}>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.stage")}</TableHead>
                <TableHead>{t("reports.durations")}</TableHead>
                <TableHead>{t("reports.sampleCount")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stages.map((stage) => (
                <TableRow key={stage}>
                  <TableCell>{t(`stage.${stage}`)}</TableCell>
                  <TableCell>
                    {metrics.stage_duration[stage].days === null
                      ? t("reports.undefined")
                      : reportNumber(metrics.stage_duration[stage].days)}
                  </TableCell>
                  <TableCell>{reportNumber(metrics.stage_duration[stage].sample_count)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Table aria-label={t("reports.activities")}>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.activities")}</TableHead>
                <TableHead>{t("reports.count")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activityTypes.map((activity) => (
                <TableRow key={activity}>
                  <TableCell>{t(`profile.activity.${activity}`)}</TableCell>
                  <TableCell>{reportNumber(metrics.activities[activity])}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </details>
    </>
  );
}

export function AgreementCard({ agreement }: { agreement: Agreement }) {
  return (
    <section
      aria-label={t("reports.agreement")}
      className="space-y-3 rounded-lg border bg-card p-5"
    >
      <h2 className="text-lg font-semibold">{t("reports.agreement")}</h2>
      <p className="text-3xl font-semibold tabular-nums">{reportRate(agreement.rate)}</p>
      <p>
        {t("reports.agreementCounts")
          .replace("{agree}", reportNumber(agreement.agree))
          .replace("{disagree}", reportNumber(agreement.disagree))
          .replace("{total}", reportNumber(agreement.total))}
      </p>
      <p className="text-sm text-muted-foreground">{t("reports.agreementHelp")}</p>
    </section>
  );
}

const columns = [
  "name",
  "new_cvs",
  "screened",
  "submitted",
  "interviews",
  "placements",
  "agreement",
] as const;
type Column = (typeof columns)[number];
export function RecruiterTable({ items }: { items: RecruiterRow[] }) {
  const [sort, setSort] = useState<{ column: Column; asc: boolean }>({ column: "name", asc: true });
  const value = (item: RecruiterRow, column: Column) =>
    column === "name"
      ? (item.recruiter_name ?? t("reports.unassigned"))
      : column === "agreement"
        ? item.metrics.ai_agreement.rate
        : column === "interviews"
          ? item.metrics.interviews.total
          : item.metrics[column];
  const rows = [...items].sort((a, b) => {
    const left = value(a, sort.column),
      right = value(b, sort.column);
    if (left === null) return right === null ? 0 : 1;
    if (right === null) return -1;
    const comparison =
      typeof left === "string" && typeof right === "string"
        ? left.localeCompare(right, "vi")
        : Number(left) - Number(right);
    return (sort.asc ? 1 : -1) * comparison;
  });
  return (
    <section
      aria-label={t("reports.recruiters")}
      className="min-w-0 space-y-4 rounded-lg border bg-card p-5"
    >
      <h2 className="text-lg font-semibold">{t("reports.recruiters")}</h2>
      <Table aria-label={t("reports.recruiters")}>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead
                key={column}
                aria-sort={
                  sort.column === column ? (sort.asc ? "ascending" : "descending") : "none"
                }
              >
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setSort({ column, asc: sort.column === column ? !sort.asc : true })
                  }
                >
                  {t(`reports.${column}`)}
                </Button>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7}>{t("reports.noRecruiters")}</TableCell>
            </TableRow>
          ) : (
            rows.map((item) => (
              <TableRow key={item.recruiter_id ?? "unassigned"}>
                {columns.map((column) => (
                  <TableCell
                    key={column}
                    className={column === "name" ? "max-w-48 truncate" : "tabular-nums"}
                    title={
                      column === "name"
                        ? (item.recruiter_name ?? t("reports.unassigned"))
                        : undefined
                    }
                  >
                    {column === "name"
                      ? value(item, column)
                      : column === "agreement"
                        ? reportRate(item.metrics.ai_agreement.rate)
                        : reportNumber(Number(value(item, column)))}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </section>
  );
}
