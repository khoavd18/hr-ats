"use client";

import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import {
  emailVariables,
  type EmailPreview,
  type EmailTemplate,
  type PreviewOption,
} from "@/lib/email-types";
import { t } from "@/i18n/vi";

const stages = [
  "new",
  "screening",
  "submitted",
  "interview",
  "offer",
  "hired",
  "rejected",
  "withdrawn",
] as const;
const selectStyle = "h-10 w-full rounded-md border bg-background px-3";

export function EmailTemplatesSettings() {
  const { user } = useAuth();
  const allowed = user?.role === "admin" || user?.role === "lead";
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<EmailTemplate | "new" | null>(null);
  const templates = useQuery({
    queryKey: ["email-templates", page],
    queryFn: ({ signal }) =>
      api<{ items: EmailTemplate[]; total: number }>(`/email-templates?page=${page}&page_size=20`, {
        signal,
      }),
    enabled: allowed,
    retry: false,
  });
  if (!allowed) return null;
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("emailTemplates.title")}
        description={t("emailTemplates.description")}
        action={<Button onClick={() => setEditing("new")}>{t("emailTemplates.create")}</Button>}
      />
      <QueryFeedback
        pending={templates.isPending}
        error={templates.error}
        retry={() => void templates.refetch()}
      />
      {templates.data && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("emailTemplates.name")}</TableHead>
                <TableHead>{t("emailTemplates.stage")}</TableHead>
                <TableHead>{t("emailTemplates.status")}</TableHead>
                <TableHead>{t("emailTemplates.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.data.items.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="max-w-64 truncate" title={row.name}>
                    {row.name}
                  </TableCell>
                  <TableCell>
                    {row.stage ? t(`stage.${row.stage}`) : t("emailTemplates.noStage")}
                  </TableCell>
                  <TableCell>
                    {t(row.is_active ? "emailTemplates.active" : "emailTemplates.inactive")}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      onClick={() => setEditing(row)}
                      aria-label={`${t("emailTemplates.edit")} ${row.name}`}
                    >
                      {t("emailTemplates.edit")}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {templates.data.total === 0 && <p>{t("emailTemplates.empty")}</p>}
          <div className="flex items-center gap-3">
            <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>
              {t("users.previous")}
            </Button>
            <span>{page}</span>
            <Button
              variant="outline"
              disabled={page * 20 >= templates.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("users.next")}
            </Button>
          </div>
        </>
      )}
      {editing && (
        <TemplateEditor
          key={editing === "new" ? "new" : editing.id}
          initial={editing === "new" ? null : editing}
          close={() => setEditing(null)}
          saved={() => void queryClient.invalidateQueries({ queryKey: ["email-templates"] })}
        />
      )}
    </div>
  );
}

function TemplateEditor({
  initial,
  close,
  saved,
}: {
  initial: EmailTemplate | null;
  close: () => void;
  saved: () => void;
}) {
  const [row, setRow] = useState(initial);
  const [draft, setDraft] = useState({
    name: initial?.name ?? "",
    subject: initial?.subject ?? "",
    body: initial?.body ?? "",
    stage: initial?.stage ?? "",
    is_active: initial?.is_active ?? true,
  });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [preview, setPreview] = useState<EmailPreview | null>(null);
  const [applicationId, setApplicationId] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [optionPage, setOptionPage] = useState(1);
  const subjectRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const target = useRef<"subject" | "body">("body");
  const insertion = useRef<{ field: "subject" | "body"; caret: number } | null>(null);
  const alive = useRef(true);
  const requestRef = useRef<AbortController | null>(null);
  useLayoutEffect(() => {
    const selection = insertion.current;
    if (!selection) return;
    insertion.current = null;
    const input = selection.field === "subject" ? subjectRef.current : bodyRef.current;
    // Restore the caret after the value commits, before another interaction can change focus.
    input?.focus();
    input?.setSelectionRange(selection.caret, selection.caret);
  }, [draft]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      requestRef.current?.abort();
    };
  }, []);
  const options = useQuery({
    queryKey: ["email-preview-options", q, optionPage],
    queryFn: ({ signal }) =>
      api<{ items: PreviewOption[]; total: number }>(
        `/email-templates/preview-options?page=${optionPage}&page_size=20&q=${encodeURIComponent(q)}`,
        { signal },
      ),
    enabled: row !== null,
    retry: false,
    gcTime: 0,
  });
  function change(field: keyof typeof draft, value: string | boolean) {
    setDraft((current) => ({ ...current, [field]: value }));
    setPreview(null);
    setError(null);
    setNotice(null);
  }
  function insertVariable(name: (typeof emailVariables)[number]) {
    const field = target.current;
    const input = field === "subject" ? subjectRef.current : bodyRef.current;
    const start = input?.selectionStart ?? draft[field].length;
    const end = input?.selectionEnd ?? start;
    const value = `{{ ${name} }}`;
    insertion.current = { field, caret: start + value.length };
    change(field, draft[field].slice(0, start) + value + draft[field].slice(end));
  }
  async function perform(mode: "save" | "preview") {
    if (pending) return;
    if (!draft.name.trim() || !draft.subject.trim() || !draft.body.trim()) {
      setError(t("emailTemplates.required"));
      (draft.name.trim()
        ? draft.subject.trim()
          ? bodyRef.current
          : subjectRef.current
        : document.getElementById("email-template-name")
      )?.focus();
      return;
    }
    const controller = new AbortController();
    requestRef.current = controller;
    setPending(true);
    setError(null);
    setPreview(null);
    setNotice(null);
    try {
      if (mode === "save") {
        const result = await api<EmailTemplate>(
          row ? `/email-templates/${row.id}` : "/email-templates",
          {
            method: row ? "PATCH" : "POST",
            signal: controller.signal,
            body: JSON.stringify({
              ...draft,
              stage: draft.stage || null,
              ...(row ? {} : { key: `custom_${crypto.randomUUID().replaceAll("-", "")}` }),
            }),
          },
        );
        if (!alive.current) return;
        setRow(result);
        setNotice(t("emailTemplates.saved"));
        saved();
      } else if (row && applicationId) {
        const result = await api<EmailPreview>(`/email-templates/${row.id}/preview`, {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            application_id: applicationId,
            subject: draft.subject,
            body: draft.body,
          }),
        });
        if (alive.current) setPreview(result);
      }
    } catch (err) {
      if (alive.current && !controller.signal.aborted)
        setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      if (alive.current) setPending(false);
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void perform("save");
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) close();
      }}
    >
      <DialogContent
        closeDisabled={pending}
        className="max-h-[90vh] max-w-4xl overflow-y-auto"
        onEscapeKeyDown={(event) => {
          if (pending) event.preventDefault();
        }}
        onInteractOutside={(event) => {
          if (pending) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t(row ? "emailTemplates.edit" : "emailTemplates.create")}</DialogTitle>
          <DialogDescription>{t("emailTemplates.hint")}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="space-y-4">
          <fieldset disabled={pending} className="space-y-4">
            <label className="block" htmlFor="email-template-name">
              {t("emailTemplates.name")}
            </label>
            <Input
              id="email-template-name"
              value={draft.name}
              maxLength={200}
              onChange={(e) => change("name", e.target.value)}
            />
            <label className="block" htmlFor="email-template-stage">
              {t("emailTemplates.stage")}
            </label>
            <select
              id="email-template-stage"
              className={selectStyle}
              value={draft.stage}
              onChange={(e) => change("stage", e.target.value)}
            >
              <option value="">{t("emailTemplates.noStage")}</option>
              {stages.map((stage) => (
                <option key={stage} value={stage}>
                  {t(`stage.${stage}`)}
                </option>
              ))}
            </select>
            <label className="block" htmlFor="email-template-subject">
              {t("emailTemplates.subject")}
            </label>
            <Input
              id="email-template-subject"
              ref={subjectRef}
              value={draft.subject}
              maxLength={500}
              onFocus={() => {
                target.current = "subject";
              }}
              onChange={(e) => change("subject", e.target.value)}
            />
            <label className="block" htmlFor="email-template-body">
              {t("emailTemplates.body")}
            </label>
            <textarea
              id="email-template-body"
              ref={bodyRef}
              className="min-h-48 w-full rounded-md border bg-background p-3"
              value={draft.body}
              maxLength={20000}
              onFocus={() => {
                target.current = "body";
              }}
              onChange={(e) => change("body", e.target.value)}
            />
            <div
              role="group"
              aria-label={t("emailTemplates.variables")}
              className="flex flex-wrap gap-2"
            >
              {emailVariables.map((name) => (
                <Button
                  key={name}
                  type="button"
                  variant="outline"
                  size="sm"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => insertVariable(name)}
                >
                  {t(`emailTemplates.variable.${name}`)}
                </Button>
              ))}
            </div>
            <label className="flex gap-2">
              <input
                type="checkbox"
                checked={draft.is_active}
                onChange={(e) => change("is_active", e.target.checked)}
              />
              {t("emailTemplates.active")}
            </label>
            <p className="text-sm text-muted-foreground">
              {t(
                row?.requires_confirmation === false
                  ? "emailTemplates.receiptNotice"
                  : "emailTemplates.confirmation",
              )}
            </p>
            <Button type="submit">{t(pending ? "common.processing" : "common.save")}</Button>
          </fieldset>
        </form>
        {notice && <p role="status">{notice}</p>}
        {error && <p role="alert">{error}</p>}
        <section aria-label={t("emailTemplates.preview")} className="space-y-3 border-t pt-4">
          <p>{t("emailTemplates.previewNotice")}</p>
          {!row ? (
            <p>{t("emailTemplates.saveFirst")}</p>
          ) : (
            <>
              <div className="flex gap-2">
                <Input
                  aria-label={t("emailTemplates.search")}
                  value={search}
                  maxLength={200}
                  disabled={pending}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <Button
                  type="button"
                  variant="outline"
                  disabled={pending}
                  onClick={() => {
                    setQ(search);
                    setOptionPage(1);
                    setApplicationId("");
                    setPreview(null);
                  }}
                >
                  {t("emailTemplates.find")}
                </Button>
              </div>
              <QueryFeedback
                pending={options.isPending}
                error={options.error}
                retry={() => void options.refetch()}
              />
              {options.data && (
                <>
                  <label className="block" htmlFor="email-preview-application">
                    {t("emailTemplates.previewCandidate")}
                  </label>
                  <select
                    id="email-preview-application"
                    className={selectStyle}
                    value={applicationId}
                    disabled={pending}
                    onChange={(e) => {
                      setApplicationId(e.target.value);
                      setPreview(null);
                      setError(null);
                    }}
                  >
                    <option value="">{t("emailTemplates.chooseCandidate")}</option>
                    {options.data.items.map((option) => (
                      <option
                        key={option.id}
                        value={option.id}
                      >{`${option.candidate_name} · ${option.job_title}`}</option>
                    ))}
                  </select>
                  {options.data.total === 0 && <p>{t("emailTemplates.noCandidates")}</p>}
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={pending || optionPage === 1}
                      onClick={() => {
                        setOptionPage(optionPage - 1);
                        setApplicationId("");
                        setPreview(null);
                      }}
                    >
                      {t("users.previous")}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={pending || optionPage * 20 >= options.data.total}
                      onClick={() => {
                        setOptionPage(optionPage + 1);
                        setApplicationId("");
                        setPreview(null);
                      }}
                    >
                      {t("users.next")}
                    </Button>
                  </div>
                </>
              )}
              <Button
                type="button"
                disabled={pending || !applicationId}
                onClick={() => void perform("preview")}
              >
                {t("emailTemplates.preview")}
              </Button>
            </>
          )}
          {preview && (
            <div className="space-y-2 rounded-md border p-3">
              <p className="break-words">{preview.subject}</p>
              <iframe
                title={t("emailTemplates.preview")}
                sandbox=""
                className="h-64 w-full border bg-white"
                srcDoc={`<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; base-uri 'none'; form-action 'none'"><meta charset="utf-8">${preview.body_html}`}
              />
            </div>
          )}
        </section>
        <Button type="button" variant="outline" disabled={pending} onClick={close}>
          {t("common.close")}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
