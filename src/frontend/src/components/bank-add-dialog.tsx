"use client";

import { useId, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { QueryFeedback } from "@/components/query-feedback";
import { BankCandidateCard } from "@/components/bank-candidate-card";
import { api, ApiError } from "@/lib/api";
import type { CandidateBrief, CandidateList } from "@/lib/cv-bank-types";
import type { Job } from "@/lib/job-types";
import { t } from "@/i18n/vi";

function AddCandidatesAction({
  candidates,
  jobId,
  onAdded,
  onPending,
}: {
  candidates: CandidateBrief[];
  jobId: string;
  onAdded: (ids: string[]) => void;
  onPending: (value: boolean) => void;
}) {
  const client = useQueryClient();
  const [pending, setPending] = useState(false);
  const running = useRef(false);
  const [results, setResults] = useState<{ id: string; name: string; message: string }[]>([]);
  async function add() {
    if (running.current) return;
    running.current = true;
    setPending(true);
    onPending(true);
    setResults([]);
    const added: string[] = [];
    try {
      for (const candidate of candidates) {
        let message: string;
        try {
          const result = await api<{ ai_status: string }>("/applications", {
            method: "POST",
            body: JSON.stringify({ candidate_id: candidate.id, job_id: jobId }),
          });
          added.push(candidate.id);
          message = t(result.ai_status === "failed" ? "bank.addedScoreFailed" : "bank.added");
        } catch (error) {
          if (error instanceof ApiError && error.code === "APPLICATION_EXISTS") {
            added.push(candidate.id);
            message = t("bank.alreadyAdded");
          } else message = error instanceof ApiError ? error.message : t("api.unknown");
        }
        setResults((items) => [...items, { id: candidate.id, name: candidate.full_name, message }]);
      }
      onAdded(added);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["job-ranking", jobId] }),
        client.invalidateQueries({ queryKey: ["job", jobId] }),
        client.invalidateQueries({ queryKey: ["jobs"] }),
        client.invalidateQueries({ queryKey: ["bank-suggestions", jobId] }),
      ]);
    } finally {
      running.current = false;
      setPending(false);
      onPending(false);
    }
  }
  return (
    <div className="space-y-3 border-t pt-4">
      <p className="text-sm text-muted-foreground">{t("bank.addHint")}</p>
      <Button disabled={!jobId || candidates.length === 0 || pending} onClick={add}>
        {t(pending ? "common.processing" : "bank.addSelected")}
      </Button>
      <ul aria-live="polite" className="space-y-2 text-sm">
        {results.map((result) => (
          <li key={result.id}>
            {result.name}
            {t("common.separator")}
            {result.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AddToJobDialog({
  candidates,
  onAdded,
}: {
  candidates: CandidateBrief[];
  onAdded: (ids: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!pending) setOpen(value);
      }}
    >
      <DialogTrigger asChild>
        <Button disabled={candidates.length === 0}>{t("bank.addToJob")}</Button>
      </DialogTrigger>
      <DialogContent
        closeDisabled={pending}
        onEscapeKeyDown={(e) => {
          if (pending) e.preventDefault();
        }}
        onInteractOutside={(e) => {
          if (pending) e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("bank.addToJob")}</DialogTitle>
          <DialogDescription>{t("bank.chooseJobHint")}</DialogDescription>
        </DialogHeader>
        {open && (
          <JobChooser
            candidates={candidates}
            onAdded={onAdded}
            onPending={setPending}
            pending={pending}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function JobChooser({
  candidates,
  onAdded,
  onPending,
  pending,
}: {
  candidates: CandidateBrief[];
  onAdded: (ids: string[]) => void;
  onPending: (value: boolean) => void;
  pending: boolean;
}) {
  const jobSelectId = useId();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [jobId, setJobId] = useState("");
  const jobs = useQuery({
    queryKey: ["bank-job-choices", q, page],
    queryFn: ({ signal }) =>
      api<{ items: Job[]; total: number }>(
        `/jobs?${new URLSearchParams({ q, page: String(page), page_size: "20" })}`,
        { signal },
      ),
    retry: false,
  });
  return (
    <div className="space-y-4">
      <label className="block space-y-2">
        <span>{t("bank.jobSearch")}</span>
        <Input
          disabled={pending}
          value={q}
          maxLength={200}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
            setJobId("");
          }}
        />
      </label>
      <QueryFeedback
        pending={jobs.isPending}
        error={jobs.error}
        retry={() => {
          void jobs.refetch();
        }}
      />
      {jobs.data && !jobs.isError && (
        <>
          <div className="space-y-2">
            <label className="block" htmlFor={jobSelectId}>
              {t("bank.chooseJob")}
            </label>
            <select
              id={jobSelectId}
              className="h-10 w-full rounded-md border bg-background px-3"
              disabled={pending}
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
            >
              <option value="">{t("bank.chooseJob")}</option>
              {jobs.data.items.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title}
                </option>
              ))}
            </select>
          </div>
          {jobs.data.items.length === 0 && <p>{t("bank.noJobs")}</p>}
          <div className="flex gap-3">
            <Button
              variant="outline"
              disabled={page === 1 || pending}
              onClick={() => {
                setPage(page - 1);
                setJobId("");
              }}
            >
              {t("users.previous")}
            </Button>
            <Button
              variant="outline"
              disabled={page * 20 >= jobs.data.total || pending}
              onClick={() => {
                setPage(page + 1);
                setJobId("");
              }}
            >
              {t("users.next")}
            </Button>
          </div>
        </>
      )}
      <AddCandidatesAction
        key={jobId}
        candidates={candidates}
        jobId={jobId}
        onAdded={onAdded}
        onPending={onPending}
      />
    </div>
  );
}

export function AddFromBank({ jobId }: { jobId: string }) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!pending) setOpen(value);
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline">{t("bank.fromBank")}</Button>
      </DialogTrigger>
      <DialogContent
        className="max-h-[90vh] max-w-4xl overflow-y-auto"
        closeDisabled={pending}
        onEscapeKeyDown={(e) => {
          if (pending) e.preventDefault();
        }}
        onInteractOutside={(e) => {
          if (pending) e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("bank.fromBank")}</DialogTitle>
          <DialogDescription>{t("bank.suggestionsHint")}</DialogDescription>
        </DialogHeader>
        {open && <SuggestionPicker jobId={jobId} onPending={setPending} pending={pending} />}
      </DialogContent>
    </Dialog>
  );
}

function SuggestionPicker({
  jobId,
  onPending,
  pending,
}: {
  jobId: string;
  onPending: (value: boolean) => void;
  pending: boolean;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const suggestions = useQuery({
    queryKey: ["bank-suggestions", jobId],
    queryFn: ({ signal }) => api<CandidateList>(`/jobs/${jobId}/suggestions?limit=50`, { signal }),
    retry: false,
    staleTime: 0,
  });
  return (
    <div className="space-y-4">
      <QueryFeedback
        pending={suggestions.isPending}
        error={suggestions.error}
        retry={() => {
          void suggestions.refetch();
        }}
      />
      {suggestions.data && !suggestions.isError && (
        <>
          {suggestions.data.items.length === 0 && <p>{t("bank.noSuggestions")}</p>}
          <div className="grid grid-cols-2 gap-4">
            {suggestions.data.items.map((candidate) => (
              <BankCandidateCard key={candidate.id} candidate={candidate}>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    disabled={pending}
                    checked={selected.includes(candidate.id)}
                    onChange={(e) =>
                      setSelected((ids) =>
                        e.target.checked
                          ? [...ids, candidate.id]
                          : ids.filter((id) => id !== candidate.id),
                      )
                    }
                  />
                  <span>
                    {t("bank.select")}
                    {candidate.full_name}
                  </span>
                </label>
              </BankCandidateCard>
            ))}
          </div>
        </>
      )}
      <AddCandidatesAction
        candidates={
          suggestions.isError
            ? []
            : (suggestions.data?.items ?? []).filter((c) => selected.includes(c.id))
        }
        jobId={jobId}
        onPending={onPending}
        onAdded={(ids) => setSelected((current) => current.filter((id) => !ids.includes(id)))}
      />
    </div>
  );
}
