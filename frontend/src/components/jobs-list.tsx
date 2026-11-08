"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { jobStatuses, type Job, type JobOptions } from "@/lib/job-types";
import { t } from "@/i18n/vi";

export function JobsList() {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [owner, setOwner] = useState("");
  const options = useQuery({
    queryKey: ["job-options"],
    queryFn: ({ signal }) => api<JobOptions>("/jobs/options", { signal }),
    retry: false,
  });
  const jobs = useQuery({
    queryKey: ["jobs", page, q, status, owner],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ page: String(page), page_size: "20", q });
      if (status) params.set("status", status);
      if (owner) params.set("owner_id", owner);
      return api<{ items: Job[]; total: number }>(`/jobs?${params}`, { signal });
    },
    retry: false,
  });
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.jobs")}
        description={t("jobs.description")}
        action={
          <Button asChild>
            <Link href="/jobs/new">{t("jobs.create")}</Link>
          </Button>
        }
      />
      <div className="flex flex-wrap items-end gap-4 rounded-lg border bg-card p-4">
        <div className="flex-1 space-y-2">
          <label htmlFor="job-search">{t("jobs.search")}</label>
          <Input
            id="job-search"
            value={q}
            maxLength={200}
            onChange={(event) => {
              setQ(event.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="job-status" className="block">
            {t("jobs.status")}
          </label>
          <select
            id="job-status"
            className="h-10 rounded-md border bg-background px-3"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("jobs.allStatuses")}</option>
            {jobStatuses.map((value) => (
              <option key={value} value={value}>
                {t(`jobs.${value}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label htmlFor="job-owner" className="block">
            {t("jobs.owner")}
          </label>
          <select
            id="job-owner"
            className="h-10 max-w-64 rounded-md border bg-background px-3"
            value={owner}
            onChange={(event) => {
              setOwner(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("jobs.allOwners")}</option>
            {options.data?.users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <QueryFeedback
        pending={jobs.isPending}
        error={jobs.error ?? options.error}
        retry={() => {
          void jobs.refetch();
          void options.refetch();
        }}
      />
      {jobs.data && (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  {(["title", "unit", "owner", "deadline", "status", "actions"] as const).map(
                    (key) => (
                      <TableHead key={key}>{t(`jobs.${key}`)}</TableHead>
                    ),
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-10 text-center">
                      <p>{t("jobs.emptyTitle")}</p>
                      <p className="mt-2 text-sm text-muted-foreground">{t("jobs.emptyHint")}</p>
                      <Button asChild variant="outline" className="mt-4">
                        <Link href="/jobs/new">{t("jobs.create")}</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                )}
                {jobs.data.items.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="max-w-64 truncate font-medium" title={job.title}>
                      <Link
                        className="text-primary underline-offset-4 hover:underline"
                        href={`/jobs/${job.id}/edit`}
                      >
                        {job.title}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-44 truncate" title={job.hiring_unit_name}>
                      {job.hiring_unit_name}
                    </TableCell>
                    <TableCell className="max-w-44 truncate" title={job.owner_name}>
                      {job.owner_name}
                    </TableCell>
                    <TableCell>
                      {job.deadline
                        ? new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }).format(
                            new Date(`${job.deadline}T00:00:00+07:00`),
                          )
                        : t("jobs.noDeadline")}
                    </TableCell>
                    <TableCell>
                      <Badge variant={job.status === "open" ? "secondary" : "outline"}>
                        {t(`jobs.${job.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button asChild variant="outline" size="sm">
                        <Link href={`/jobs/${job.id}/edit`}>{t("jobs.edit")}</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>
              {t("users.previous")}
            </Button>
            <Button
              variant="outline"
              disabled={page * 20 >= jobs.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("users.next")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
