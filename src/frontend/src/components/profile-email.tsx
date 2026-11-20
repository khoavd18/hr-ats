"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { EmailCompose } from "@/components/email-compose";
import { EmailHtml } from "@/components/email-html";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { EmailDraft, EmailMessage } from "@/lib/email-types";
import { t } from "@/i18n/vi";

export function ProfileEmail({
  applicationId,
  email,
}: {
  applicationId: string;
  email: string | null;
}) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [template, setTemplate] = useState("");
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const lock = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const messages = useQuery({
    queryKey: ["application-emails", applicationId, page],
    queryFn: ({ signal }) =>
      api<{ items: EmailMessage[]; total: number }>(
        `/email-messages?application_id=${applicationId}&page=${page}`,
        { signal },
      ),
    enabled: open,
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchInterval: open ? 3000 : false,
  });
  const templates = useQuery({
    queryKey: ["send-email-templates", applicationId],
    queryFn: ({ signal }) =>
      api<{ items: { id: string; name: string }[] }>(
        `/email-messages/templates?application_id=${applicationId}`,
        { signal },
      ),
    enabled: open,
    retry: false,
    gcTime: 0,
  });
  async function action(run: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      await run();
    } catch (err) {
      if (mounted.current) setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  async function change(row: EmailMessage, target: "send" | "cancel") {
    await api(`/email-messages/${row.id}/${target}`, { method: "POST" });
    if (!mounted.current) return;
    void client.invalidateQueries({ queryKey: ["application-emails", applicationId] });
    void client.invalidateQueries({ queryKey: ["application-profile", applicationId] });
  }
  return (
    <section aria-label={t("email.title")} className="space-y-3 border-t pt-5">
      <h2>
        <Button variant="outline" aria-expanded={open} onClick={() => setOpen(!open)}>
          {t("email.title")}
        </Button>
      </h2>
      {open && (
        <>
          {!email && <p role="status">{t("email.noAddress")}</p>}
          <Button
            disabled={busy}
            onClick={() =>
              setDraft({
                application_id: applicationId,
                template_id: null,
                to_email: email ?? "",
                subject: "",
                body: "",
                body_html: "",
                has_calendar: false,
              })
            }
          >
            {t("email.compose")}
          </Button>
          <QueryFeedback
            pending={templates.isPending}
            error={templates.error}
            retry={() => {
              void templates.refetch();
            }}
          />
          {templates.data && (
            <div className="flex flex-wrap items-end gap-2">
              <label className="min-w-0 flex-1 space-y-1">
                <span>{t("email.template")}</span>
                <select
                  className="h-10 w-full rounded-md border bg-background px-2"
                  disabled={busy}
                  value={template}
                  onChange={(event) => setTemplate(event.target.value)}
                >
                  <option value="">{t("email.free")}</option>
                  {templates.data.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                disabled={busy || !template}
                onClick={() =>
                  void action(async () => {
                    const result = await api<EmailDraft>("/email-messages/preview", {
                      method: "POST",
                      body: JSON.stringify({
                        application_id: applicationId,
                        template_id: template,
                      }),
                    });
                    if (mounted.current) setDraft(result);
                  })
                }
              >
                {t("email.useTemplate")}
              </Button>
            </div>
          )}
          <QueryFeedback
            pending={messages.isPending}
            error={messages.error}
            retry={() => {
              void messages.refetch();
            }}
          />
          {error && <p role="alert">{error}</p>}
          {messages.data && !messages.isError && (
            <>
              {messages.data.items.length === 0 && <p>{t("email.empty")}</p>}
              <ul className="space-y-3">
                {messages.data.items.map((row) => (
                  <li key={row.id} className="rounded-md border p-3 text-sm">
                    <p>{t(`email.status.${row.status}`)}</p>
                    <details className="break-words">
                      <summary className="cursor-pointer font-medium">{row.subject}</summary>
                      <p>
                        {t("email.to")}
                        {t("common.separator")}
                        {row.to_email}
                      </p>
                      <time dateTime={row.sent_at ?? row.created_at}>
                        {new Intl.DateTimeFormat("vi-VN", {
                          dateStyle: "short",
                          timeStyle: "short",
                          timeZone: "Asia/Ho_Chi_Minh",
                        }).format(new Date(row.sent_at ?? row.created_at))}
                      </time>
                      <EmailHtml html={row.body_html} />
                      {row.status === "failed" && <p>{t("email.failed")}</p>}
                      {row.status === "failed" && row.scheduled_for && <p>{t("email.retrying")}</p>}
                      <div className="mt-2 flex flex-wrap gap-2">
                        {(row.status === "failed" || row.status === "draft") && (
                          <Button
                            disabled={busy}
                            onClick={() => void action(() => change(row, "send"))}
                          >
                            {t(row.status === "failed" ? "email.retry" : "email.send")}
                          </Button>
                        )}
                        {["draft", "queued", "failed"].includes(row.status) && (
                          <Button
                            variant="outline"
                            disabled={busy}
                            onClick={() => void action(() => change(row, "cancel"))}
                          >
                            {t("email.cancel")}
                          </Button>
                        )}
                      </div>
                    </details>
                  </li>
                ))}
              </ul>
              {messages.data.total > 20 && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    disabled={page === 1 || busy}
                    onClick={() => setPage(page - 1)}
                  >
                    {t("email.previous")}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={page * 20 >= messages.data.total || busy}
                    onClick={() => setPage(page + 1)}
                  >
                    {t("email.next")}
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      )}
      {draft && <EmailCompose draft={draft} onClose={() => setDraft(null)} />}
    </section>
  );
}
