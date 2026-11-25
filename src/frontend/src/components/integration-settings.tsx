"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { Badge } from "@/components/ui/badge";
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
import { api } from "@/lib/api";

type Kind = "cv-scored" | "pipeline" | "overdue" | "daily-report";
type Notification = { kind: Kind; enabled: boolean };
type Delivery = {
  id: string;
  kind: Kind;
  is_test: boolean;
  created_at: string;
  status: "sent" | "failed" | "paused" | "retrying" | "pending";
  error_code: "WEBHOOK_DELIVERY_FAILED" | null;
};
type IntegrationSettingsData = {
  available: boolean;
  notifications: Notification[];
  history: Delivery[];
};
type Action = { kind: Kind; enabled: boolean } | { kind: Kind; test: true };

const path = "/settings/integrations";
const queryKey = ["integration-settings"];
const formatter = new Intl.DateTimeFormat("vi-VN", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "Asia/Ho_Chi_Minh",
});

export function IntegrationSettings() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => api<IntegrationSettingsData>(path, { signal }),
    refetchInterval: 5000,
  });
  const action = useMutation({
    mutationFn: (input: Action) =>
      "test" in input
        ? api(`${path}/${input.kind}/test`, { method: "POST" })
        : api(`${path}/${input.kind}`, {
            method: "PUT",
            body: JSON.stringify({ enabled: input.enabled }),
          }),
    onSuccess: async () => client.invalidateQueries({ queryKey }),
  });
  const data = query.data;
  return (
    <div className="space-y-6">
      <PageHeader title={t("integrations.title")} description={t("integrations.description")} />
      <QueryFeedback
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {data && !query.isError && (
        <>
          {!data.available && (
            <p className="rounded-lg border bg-muted p-4 text-sm" role="status">
              {t("integrations.unavailable")}
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {data.notifications.map(({ kind, enabled }) => (
              <section
                key={kind}
                aria-labelledby={`notification-${kind}`}
                className="space-y-3 rounded-lg border bg-card p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 id={`notification-${kind}`} className="font-medium">
                    {t(`integrations.kind.${kind}`)}
                  </h2>
                  <Badge variant={enabled ? "default" : "secondary"}>
                    {t(enabled ? "integrations.enabled" : "integrations.disabled")}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={action.isPending}
                    onClick={() => action.mutate({ kind, enabled: !enabled })}
                  >
                    {t(enabled ? "integrations.disable" : "integrations.enable")}
                  </Button>
                  <Button
                    size="sm"
                    disabled={!data.available || !enabled || action.isPending}
                    onClick={() => action.mutate({ kind, test: true })}
                  >
                    {t("integrations.test")}
                  </Button>
                </div>
              </section>
            ))}
          </div>
          {action.isError && (
            <p role="alert" className="text-sm text-destructive">
              {action.error.message}
            </p>
          )}
          {action.isSuccess && action.variables && "test" in action.variables && (
            <p role="status" className="text-sm">
              {t("integrations.testQueued")}
            </p>
          )}
          <section aria-labelledby="integration-history" className="space-y-3">
            <h2 id="integration-history" className="text-lg font-semibold">
              {t("integrations.history")}
            </h2>
            {data.history.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("integrations.historyEmpty")}</p>
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("integrations.time")}</TableHead>
                      <TableHead>{t("integrations.notification")}</TableHead>
                      <TableHead>{t("integrations.state")}</TableHead>
                      <TableHead>{t("integrations.error")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.history.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="whitespace-nowrap">
                          <time dateTime={entry.created_at}>
                            {formatter.format(new Date(entry.created_at))}
                          </time>
                        </TableCell>
                        <TableCell>
                          {t(`integrations.kind.${entry.kind}`)}
                          {entry.is_test && (
                            <span className="ml-2 text-muted-foreground">
                              {t("integrations.testEntry")}
                            </span>
                          )}
                        </TableCell>
                        <TableCell>{t(`integrations.status.${entry.status}`)}</TableCell>
                        <TableCell>{entry.error_code ?? t("integrations.noError")}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
