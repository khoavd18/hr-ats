"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Funnel,
  FunnelChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { t } from "@/i18n/vi";
import {
  reportDate,
  reportNumber,
  reportRate,
  type DailyCVs,
  type FunnelStage,
} from "@/lib/report-types";

export function ReportFunnel({ stages }: { stages: FunnelStage[] }) {
  const flow = stages
    .filter((item) => item.stage !== "rejected" && item.stage !== "withdrawn")
    .map((item) => ({
      ...item,
      name: t(`stage.${item.stage}`),
      fill: "#2563a6",
    }));
  return (
    <section
      aria-label={t("reports.funnel")}
      className="min-w-0 space-y-4 rounded-lg border bg-card p-5"
    >
      <h2 className="text-lg font-semibold">{t("reports.funnel")}</h2>
      <p className="text-sm text-muted-foreground">{t("reports.flowHelp")}</p>
      {flow.some((item) => item.count > 0) ? (
        <div className="h-72 w-full" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%" minWidth={1}>
            <FunnelChart margin={{ top: 8, right: 135, bottom: 8, left: 8 }}>
              <Tooltip formatter={(value) => reportNumber(Number(value))} />
              <Funnel data={flow} dataKey="count" nameKey="name" isAnimationActive={false}>
                <LabelList position="right" fill="currentColor" stroke="none" dataKey="name" />
              </Funnel>
            </FunnelChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p>{t("reports.noFlow")}</p>
      )}
      <Table aria-label={t("reports.funnel")}>
        <TableHeader>
          <TableRow>
            <TableHead>{t("reports.stage")}</TableHead>
            <TableHead>{t("reports.count")}</TableHead>
            <TableHead>{t("reports.conversion")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {stages.map((item) => (
            <TableRow key={item.stage}>
              <TableCell>{t(`stage.${item.stage}`)}</TableCell>
              <TableCell>{reportNumber(item.count)}</TableCell>
              <TableCell>
                {item.next_stage ? reportRate(item.conversion_rate) : t("reports.notApplicable")}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}

export function DailyCVChart({ days }: { days: DailyCVs[] }) {
  return (
    <section
      aria-label={t("reports.daily")}
      className="min-w-0 space-y-4 rounded-lg border bg-card p-5"
    >
      <h2 className="text-lg font-semibold">{t("reports.daily")}</h2>
      {days.some((day) => day.count > 0) ? (
        <div className="h-72 w-full" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%" minWidth={1}>
            <BarChart data={days} margin={{ top: 16, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={(value: string) => reportDate(value).slice(0, 5)}
                minTickGap={25}
              />
              <YAxis allowDecimals={false} tickFormatter={reportNumber} width={65} />
              <Tooltip
                labelFormatter={(value) => reportDate(String(value))}
                formatter={(value) => [reportNumber(Number(value)), t("reports.new_cvs")]}
              />
              <Bar
                dataKey="count"
                name={t("reports.new_cvs")}
                fill="#2563a6"
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p>{t("reports.noCVs")}</p>
      )}
      <details>
        <summary className="cursor-pointer text-sm text-primary">{t("reports.dailyTable")}</summary>
        <div className="mt-3 max-h-72 overflow-auto">
          <Table aria-label={t("reports.dailyTable")}>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.date")}</TableHead>
                <TableHead>{t("reports.new_cvs")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {days.map((day) => (
                <TableRow key={day.date}>
                  <TableCell>{reportDate(day.date)}</TableCell>
                  <TableCell>{reportNumber(day.count)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </details>
    </section>
  );
}
