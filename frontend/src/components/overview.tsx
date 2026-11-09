"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { TaskRows } from "@/components/task-list";
import { CvUpload } from "@/components/cv-upload";
import { CandidateProfile } from "@/components/candidate-profile";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import type { Job } from "@/lib/job-types";
import { vietnamTime, type OverviewData } from "@/lib/task-types";
import { t } from "@/i18n/vi";

function QuickUpload() {
  const selectId = useId();
  const [open, setOpen] = useState(false);
  const [job, setJob] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const jobs = useQuery({
    queryKey: ["upload-jobs", q, page],
    queryFn: ({ signal }) =>
      api<{ items: Job[]; total: number }>(
        `/jobs?${new URLSearchParams({ q, page: String(page) })}`,
        { signal },
      ),
    enabled: open,
    retry: false,
  });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>{t("overview.upload")}</Button>
      </DialogTrigger>
      {open && (
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogTitle>{t("overview.upload")}</DialogTitle>
          <DialogDescription>{t("overview.uploadHelp")}</DialogDescription>
          <label className="space-y-1">
            <span>{t("tasks.findJob")}</span>
            <Input
              value={q}
              maxLength={200}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
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
          <div className="space-y-1">
            <label htmlFor={selectId}>{t("overview.selectJob")}</label>
            <select
              id={selectId}
              className="h-10 w-full rounded-md border"
              value={job}
              onChange={(e) => setJob(e.target.value)}
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
            <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>
              {t("common.previous")}
            </Button>
            <Button
              variant="outline"
              disabled={!jobs.data || page * 20 >= jobs.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("common.next")}
            </Button>
          </div>
          {job && <CvUpload key={job} jobId={job} />}
        </DialogContent>
      )}
    </Dialog>
  );
}

export function Overview() {
  const [profile, setProfile] = useState<string | null>(null);
  const overview = useQuery({
    queryKey: ["overview"],
    queryFn: ({ signal }) => api<OverviewData>("/overview", { signal }),
    retry: false,
    refetchInterval: 30000,
  });
  const data = overview.data;
  const total = (count: number) => t("overview.total").replace("{count}", String(count));
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.overview")}
        description={t("overview.description")}
        action={<QuickUpload />}
      />
      <QueryFeedback
        pending={overview.isPending}
        error={overview.error}
        retry={() => {
          void overview.refetch();
        }}
      />
      {data && !overview.isError && (
        <>
          <section className="rounded-xl border bg-card p-5" aria-label={t("overview.unseen")}>
            <h2 className="font-semibold">{t("overview.unseen")}</h2>
            <p className="my-2 text-3xl font-semibold">{data.unseen_cv_count}</p>
            <p className="text-sm text-muted-foreground">{t("overview.unseenHelp")}</p>
            <Link className="underline" href="/jobs">
              {t("nav.jobs")}
            </Link>
          </section>
          <div className="grid grid-cols-2 items-start gap-6">
            <section
              className="space-y-3 rounded-xl border bg-card p-5"
              aria-label={t("overview.dueTasks")}
            >
              <h2 className="font-semibold">{t("overview.dueTasks")}</h2>
              <p>{total(data.today_tasks.total)}</p>
              <TaskRows items={data.today_tasks.items} />
              <Link className="inline-block underline" href="/tasks">
                {t("overview.allTasks")}
              </Link>
            </section>
            <section
              className="space-y-3 rounded-xl border bg-card p-5"
              aria-label={t("overview.interviews")}
            >
              <h2 className="font-semibold">{t("overview.interviews")}</h2>
              <p>{total(data.interview_total)}</p>
              {!data.interviews.length && <p>{t("overview.none")}</p>}
              {data.interviews.map((item) => (
                <div key={item.id} className="min-w-0 rounded-md border p-3">
                  <Button
                    className="h-auto max-w-full whitespace-normal break-words text-left"
                    variant="link"
                    onClick={() => setProfile(item.application_id)}
                  >
                    {item.candidate_name}
                  </Button>
                  <p className="break-words">{item.job_title}</p>
                  <time dateTime={item.scheduled_at}>{vietnamTime(item.scheduled_at)}</time>
                </div>
              ))}
            </section>
            <section
              className="col-span-2 space-y-3 rounded-xl border bg-card p-5"
              aria-label={t("overview.deadlines")}
            >
              <h2 className="font-semibold">{t("overview.deadlines")}</h2>
              <p>{total(data.job_total)}</p>
              {!data.jobs.length && <p>{t("overview.none")}</p>}
              {data.jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between gap-4 rounded-md border p-3"
                >
                  <Link
                    className="min-w-0 truncate underline"
                    title={job.title}
                    href={`/jobs/${job.id}`}
                  >
                    {job.title}
                  </Link>
                  <time dateTime={job.deadline}>
                    {new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }).format(
                      new Date(`${job.deadline}T00:00:00+07:00`),
                    )}
                  </time>
                </div>
              ))}
            </section>
          </div>
        </>
      )}
      <Sheet
        open={!!profile}
        onOpenChange={(open) => {
          if (!open) setProfile(null);
        }}
      >
        <SheetContent className="w-[95vw] max-w-[1200px] overflow-y-auto sm:max-w-[1200px]">
          <SheetTitle>{t("overview.viewProfile")}</SheetTitle>
          <SheetDescription>{t("profile.description")}</SheetDescription>
          {profile && <CandidateProfile key={profile} applicationId={profile} />}
        </SheetContent>
      </Sheet>
    </div>
  );
}
