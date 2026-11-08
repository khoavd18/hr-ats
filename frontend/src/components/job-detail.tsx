"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { AiLevelBadge } from "@/components/ai-level-badge";
import { AiCounts } from "@/components/ai-counts";
import { CvUpload } from "@/components/cv-upload";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import type { Job } from "@/lib/job-types";
import { aiLevels, stages, type Ranking, type RankedApplication } from "@/lib/ranking-types";
import { t } from "@/i18n/vi";

export function JobDetail({ jobId }: { jobId: string }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [level, setLevel] = useState("");
  const [stage, setStage] = useState("");
  const [selected, setSelected] = useState<RankedApplication | null>(null);
  const drawerTrigger = useRef<HTMLButtonElement | null>(null);
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: ({ signal }) => api<Job>(`/jobs/${jobId}`, { signal }),
    retry: false,
  });
  const ranking = useQuery({
    queryKey: ["job-ranking", jobId, page, q, level, stage],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ page: String(page), page_size: "20", q });
      if (level) params.set("ai_level", level);
      if (stage) params.set("stage", stage);
      return api<Ranking>(`/jobs/${jobId}/applications?${params}`, { signal });
    },
    enabled: !!job.data && !job.isError,
    retry: false,
    refetchInterval: (query) => (query.state.error ? false : 3000),
  });
  return (
    <div className="space-y-6">
      <QueryFeedback
        pending={job.isPending}
        error={job.error}
        retry={() => {
          void job.refetch();
        }}
      />
      {job.data && !job.isError && (
        <>
          <PageHeader
            title={job.data.title}
            description={`${job.data.hiring_unit_name} · ${job.data.owner_name}`}
            action={
              <Button asChild variant="outline">
                <Link href={`/jobs/${jobId}/edit`}>{t("jobs.edit")}</Link>
              </Button>
            }
          />
          <Tabs defaultValue="candidates">
            <TabsList aria-label={t("ranking.tabs")}>
              <TabsTrigger value="candidates">{t("ranking.candidates")}</TabsTrigger>
              <TabsTrigger value="pipeline">{t("ranking.pipeline")}</TabsTrigger>
              <TabsTrigger value="info">{t("ranking.info")}</TabsTrigger>
            </TabsList>
            <TabsContent value="candidates" className="space-y-5 pt-4">
              <CvUpload jobId={jobId} />
              {ranking.data && !ranking.isError && <AiCounts counts={ranking.data.ai_counts} />}
              <div className="flex flex-wrap items-end gap-4 rounded-lg border bg-card p-4">
                <div className="min-w-48 flex-1 space-y-2">
                  <label htmlFor="candidate-search">{t("ranking.search")}</label>
                  <Input
                    id="candidate-search"
                    value={q}
                    maxLength={200}
                    onChange={(event) => {
                      setQ(event.target.value);
                      setPage(1);
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="block" htmlFor="candidate-level">
                    {t("ranking.level")}
                  </label>
                  <select
                    id="candidate-level"
                    className="h-10 rounded-md border bg-background px-3"
                    value={level}
                    onChange={(event) => {
                      setLevel(event.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="">{t("ranking.allLevels")}</option>
                    {aiLevels.map((value) => (
                      <option key={value} value={value}>
                        {t(`ai.${value}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="block" htmlFor="candidate-stage">
                    {t("ranking.stage")}
                  </label>
                  <select
                    id="candidate-stage"
                    className="h-10 rounded-md border bg-background px-3"
                    value={stage}
                    onChange={(event) => {
                      setStage(event.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="">{t("ranking.allStages")}</option>
                    {stages.map((value) => (
                      <option key={value} value={value}>
                        {t(`stage.${value}`)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <QueryFeedback
                pending={ranking.isPending}
                error={ranking.error}
                retry={() => {
                  void ranking.refetch();
                }}
              />
              {ranking.data && !ranking.isError && (
                <>
                  <div className="rounded-lg border bg-card">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {(["name", "level", "skills", "years", "stage", "received"] as const).map(
                            (key) => (
                              <TableHead key={key}>{t(`ranking.${key}`)}</TableHead>
                            ),
                          )}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {ranking.data.items.length === 0 && (
                          <TableRow>
                            <TableCell colSpan={6} className="py-10 text-center">
                              <p>
                                {t(q || stage || level ? "ranking.noMatches" : "ranking.empty")}
                              </p>
                              <p className="mt-2 text-sm text-muted-foreground">
                                {t(
                                  q || stage || level ? "ranking.filterHint" : "ranking.emptyHint",
                                )}
                              </p>
                            </TableCell>
                          </TableRow>
                        )}
                        {ranking.data.items.map((row) => (
                          <TableRow
                            key={row.id}
                            className="cursor-pointer"
                            onClick={(event) => {
                              drawerTrigger.current = event.currentTarget.querySelector("button");
                              setSelected(row);
                            }}
                          >
                            <TableCell
                              className="max-w-52 truncate font-medium"
                              title={row.candidate_name}
                            >
                              <button
                                className="text-left text-primary underline-offset-4 hover:underline focus-visible:underline"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  drawerTrigger.current = event.currentTarget;
                                  setSelected(row);
                                }}
                              >
                                {row.candidate_name}
                              </button>
                            </TableCell>
                            <TableCell>
                              {row.ai_status === "done" && row.ai_level ? (
                                <AiLevelBadge level={row.ai_level} />
                              ) : (
                                <span
                                  className={
                                    row.ai_status === "failed"
                                      ? "text-destructive"
                                      : "text-muted-foreground"
                                  }
                                >
                                  {t(
                                    row.ai_status === "failed"
                                      ? "ranking.aiFailed"
                                      : "upload.scoring",
                                  )}
                                </span>
                              )}
                            </TableCell>
                            <TableCell className="max-w-52 truncate" title={row.skills.join(", ")}>
                              {row.skills.slice(0, 4).join(", ") || t("ranking.unknown")}
                            </TableCell>
                            <TableCell>
                              {row.years_experience === null
                                ? t("ranking.unknown")
                                : new Intl.NumberFormat("vi-VN").format(
                                    Number(row.years_experience),
                                  )}
                            </TableCell>
                            <TableCell>{t(`stage.${row.stage}`)}</TableCell>
                            <TableCell>
                              {new Intl.DateTimeFormat("vi-VN", {
                                timeZone: "Asia/Ho_Chi_Minh",
                              }).format(new Date(row.created_at))}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  <div className="flex items-center justify-end gap-3">
                    <span className="text-sm text-muted-foreground">
                      {t("ranking.total")}
                      {ranking.data.total}
                    </span>
                    <Button
                      variant="outline"
                      disabled={page === 1}
                      onClick={() => setPage(page - 1)}
                    >
                      {t("users.previous")}
                    </Button>
                    <Button
                      variant="outline"
                      disabled={page * 20 >= ranking.data.total}
                      onClick={() => setPage(page + 1)}
                    >
                      {t("users.next")}
                    </Button>
                  </div>
                </>
              )}
            </TabsContent>
            <TabsContent value="pipeline">
              <p className="rounded-lg border p-6 text-muted-foreground">
                {t("ranking.pipelineHint")}
              </p>
            </TabsContent>
            <TabsContent value="info" className="space-y-4 rounded-lg border bg-card p-6">
              <p className="whitespace-pre-wrap">{job.data.description || t("ranking.unknown")}</p>
              <h2 className="font-semibold">{t("jobs.must_have")}</h2>
              <ul className="list-inside list-disc">
                {job.data.must_have.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
              <h2 className="font-semibold">{t("jobs.nice_to_have")}</h2>
              <ul className="list-inside list-disc">
                {job.data.nice_to_have.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
              <Button asChild variant="outline">
                <Link href={`/jobs/${jobId}/edit`}>{t("jobs.edit")}</Link>
              </Button>
            </TabsContent>
          </Tabs>
        </>
      )}
      <Sheet
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <SheetContent
          className="sm:max-w-lg"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            drawerTrigger.current?.focus();
          }}
        >
          <SheetHeader>
            <SheetTitle>{selected?.candidate_name ?? t("ranking.profile")}</SheetTitle>
            <SheetDescription>{t("ranking.profileHint")}</SheetDescription>
          </SheetHeader>
          {selected?.ai_level && selected.ai_status === "done" && (
            <div className="mt-6">
              <AiLevelBadge level={selected.ai_level} />
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
