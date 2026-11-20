"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { QueryFeedback } from "@/components/query-feedback";
import { api, ApiError } from "@/lib/api";
import type { Job, JobOptions } from "@/lib/job-types";
import type { User } from "@/lib/auth-types";
import { t } from "@/i18n/vi";

export function TaskCreateDialog({ applicationId }: { applicationId?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">{t("tasks.create")}</Button>
      </DialogTrigger>
      {open && <TaskForm applicationId={applicationId} close={() => setOpen(false)} />}
    </Dialog>
  );
}

function TaskForm({ applicationId, close }: { applicationId?: string; close: () => void }) {
  const formId = useId();
  const client = useQueryClient();
  const live = useRef(true);
  const saving = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const [assignee, setAssignee] = useState("");
  const [job, setJob] = useState("");
  const [application, setApplication] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [candidateQ, setCandidateQ] = useState("");
  const [candidatePage, setCandidatePage] = useState(1);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  const me = useQuery({
    queryKey: ["task-me"],
    queryFn: ({ signal }) => api<User>("/auth/me", { signal }),
    retry: false,
  });
  const options = useQuery({
    queryKey: ["job-options"],
    queryFn: ({ signal }) => api<JobOptions>("/jobs/options", { signal }),
    retry: false,
    enabled: me.data?.role === "admin" || me.data?.role === "lead",
  });
  const jobs = useQuery({
    queryKey: ["task-jobs", q, page],
    queryFn: ({ signal }) =>
      api<{ items: Job[]; total: number }>(
        `/jobs?${new URLSearchParams({ q, page: String(page) })}`,
        { signal },
      ),
    enabled: !applicationId,
    retry: false,
  });
  const candidates = useQuery({
    queryKey: ["task-applications", job, candidateQ, candidatePage],
    queryFn: ({ signal }) =>
      api<{ items: { id: string; name: string }[]; total: number }>(
        `/tasks/application-options?${new URLSearchParams({ job_id: job, q: candidateQ, page: String(candidatePage) })}`,
        { signal },
      ),
    enabled: !!job,
    retry: false,
  });
  const queryError = me.error ?? options.error ?? jobs.error ?? candidates.error;
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (saving.current || !title.trim()) return;
    saving.current = true;
    setPending(true);
    setError(null);
    try {
      await api("/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim() || null,
          due_at: due ? `${due}:00+07:00` : null,
          assignee_id: assignee || null,
          job_id: job || null,
          application_id: applicationId || application || null,
        }),
      });
      if (!live.current) return;
      await Promise.all([
        client.invalidateQueries({ queryKey: ["tasks"] }),
        client.invalidateQueries({ queryKey: ["overview"] }),
      ]);
      if (live.current) close();
    } catch (err) {
      if (live.current) setError(err instanceof Error ? err : new Error());
    } finally {
      saving.current = false;
      if (live.current) setPending(false);
    }
  }
  return (
    <DialogContent
      closeDisabled={pending}
      className="max-h-[90vh] overflow-y-auto"
      onEscapeKeyDown={(e) => {
        if (saving.current) e.preventDefault();
      }}
      onInteractOutside={(e) => {
        if (saving.current) e.preventDefault();
      }}
    >
      <DialogTitle>{t("tasks.create")}</DialogTitle>
      <DialogDescription>
        {t(applicationId ? "tasks.linkedProfile" : "tasks.createHelp")}
      </DialogDescription>
      <QueryFeedback
        pending={me.isPending || (!applicationId && jobs.isPending)}
        error={queryError}
        retry={() => {
          void me.refetch();
          if (!applicationId) void jobs.refetch();
          if (options.isEnabled) void options.refetch();
          if (job) void candidates.refetch();
        }}
      />
      <form onSubmit={save} className="space-y-4">
        <fieldset disabled={pending} className="space-y-4">
          <label className="block space-y-1">
            <span>{t("tasks.title")}</span>
            <Input
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block space-y-1">
            <span>{t("tasks.detail")}</span>
            <textarea
              className="min-h-20 w-full rounded-md border p-2"
              maxLength={10000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <label className="block space-y-1">
            <span>{t("tasks.due")}</span>
            <Input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
          </label>
          {(me.data?.role === "admin" || me.data?.role === "lead") && (
            <div className="space-y-1">
              <label htmlFor={`${formId}-assignee`}>{t("tasks.assignee")}</label>
              <select
                id={`${formId}-assignee`}
                className="h-10 w-full rounded-md border"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
              >
                <option value="">{t("tasks.me")}</option>
                {options.data?.users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {!applicationId && (
            <>
              <label className="block space-y-1">
                <span>{t("tasks.findJob")}</span>
                <Input
                  maxLength={200}
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <div className="space-y-1">
                <label htmlFor={`${formId}-job`}>{t("tasks.job")}</label>
                <select
                  id={`${formId}-job`}
                  className="h-10 w-full rounded-md border"
                  value={job}
                  onChange={(e) => {
                    setJob(e.target.value);
                    setApplication("");
                    setCandidateQ("");
                    setCandidatePage(1);
                  }}
                >
                  <option value="">{t("tasks.noLink")}</option>
                  {job && !jobs.data?.items.some((j) => j.id === job) && (
                    <option value={job}>{t("tasks.selectedJob")}</option>
                  )}
                  {jobs.data?.items.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  {t("common.previous")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={!jobs.data || page * 20 >= jobs.data.total}
                  onClick={() => setPage(page + 1)}
                >
                  {t("common.next")}
                </Button>
              </div>
              {job && (
                <>
                  <label className="block space-y-1">
                    <span>{t("tasks.findCandidate")}</span>
                    <Input
                      maxLength={200}
                      value={candidateQ}
                      onChange={(e) => {
                        setCandidateQ(e.target.value);
                        setCandidatePage(1);
                      }}
                    />
                  </label>
                  <div className="space-y-1">
                    <label htmlFor={`${formId}-candidate`}>{t("tasks.candidate")}</label>
                    <select
                      id={`${formId}-candidate`}
                      className="h-10 w-full rounded-md border"
                      value={application}
                      onChange={(e) => setApplication(e.target.value)}
                    >
                      <option value="">{t("tasks.noLink")}</option>
                      {application && !candidates.data?.items.some((a) => a.id === application) && (
                        <option value={application}>{t("tasks.selectedCandidate")}</option>
                      )}
                      {candidates.data?.items.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={candidatePage === 1}
                      onClick={() => setCandidatePage(candidatePage - 1)}
                    >
                      {t("common.previous")}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!candidates.data || candidatePage * 20 >= candidates.data.total}
                      onClick={() => setCandidatePage(candidatePage + 1)}
                    >
                      {t("common.next")}
                    </Button>
                  </div>
                </>
              )}
            </>
          )}
        </fieldset>
        {error && (
          <p role="alert">{error instanceof ApiError ? error.message : t("api.unknown")}</p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" disabled={pending} onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={pending || !me.data || !!queryError || !title.trim()}>
            {t(pending ? "common.processing" : "common.save")}
          </Button>
        </div>
      </form>
    </DialogContent>
  );
}
