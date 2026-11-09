"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { api } from "@/lib/api";
import { t } from "@/i18n/vi";

type MailboxStatus = {
  enabled: boolean;
  last_read_at: string | null;
  last_error:
    | "IMAP_NOT_CONFIGURED"
    | "IMAP_READ_FAILED"
    | "IMAP_MESSAGE_TOO_LARGE"
    | "IMAP_STATUS_UNAVAILABLE"
    | null;
};

export function MailboxSettings() {
  const { user } = useAuth();
  const allowed = user?.role === "admin" || user?.role === "lead";
  const query = useQuery({
    queryKey: ["mailbox-status"],
    queryFn: ({ signal }) => api<MailboxStatus>("/settings/mailbox", { signal }),
    enabled: allowed,
    retry: false,
    refetchInterval: 30000,
  });
  if (!allowed) return null;
  return (
    <div className="space-y-6">
      <PageHeader title={t("mailbox.title")} description={t("mailbox.description")} />
      <QueryFeedback
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && !query.isError && (
        <dl className="grid gap-3 rounded-lg border bg-card p-5 sm:grid-cols-2">
          <dt>{t("mailbox.state")}</dt>
          <dd>{t(query.data.enabled ? "mailbox.enabled" : "mailbox.disabled")}</dd>
          <dt>{t("mailbox.lastRead")}</dt>
          <dd>
            {query.data.last_read_at
              ? new Intl.DateTimeFormat("vi-VN", {
                  dateStyle: "short",
                  timeStyle: "short",
                  timeZone: "Asia/Ho_Chi_Minh",
                }).format(new Date(query.data.last_read_at))
              : t("mailbox.never")}
          </dd>
          <dt>{t("mailbox.lastError")}</dt>
          <dd role={query.data.last_error ? "status" : undefined}>
            {query.data.last_error ? t(`mailbox.${query.data.last_error}`) : t("mailbox.noError")}
          </dd>
        </dl>
      )}
    </div>
  );
}
