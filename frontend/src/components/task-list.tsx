"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { TaskCreateDialog } from "@/components/task-create-dialog";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { taskGroup, vietnamTime, type Task, type TaskList } from "@/lib/task-types";
import { t } from "@/i18n/vi";

export function TaskRows({ items }: { items: Task[] }) {
  const client = useQueryClient();
  const live = useRef(true);
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  async function complete(id: string) {
    if (busy.current) return;
    busy.current = true;
    setPendingId(id);
    setPending(true);
    setError(null);
    try {
      await api(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ status: "done" }) });
      if (live.current)
        await Promise.all([
          client.invalidateQueries({ queryKey: ["tasks"] }),
          client.invalidateQueries({ queryKey: ["overview"] }),
          client.invalidateQueries({ queryKey: ["application-profile"] }),
        ]);
    } catch (err) {
      if (live.current) setError(err instanceof Error ? err : new Error());
    } finally {
      busy.current = false;
      if (live.current) {
        setPending(false);
        setPendingId(null);
      }
    }
  }
  return (
    <div className="space-y-2">
      {error && <p role="alert">{error instanceof ApiError ? error.message : t("api.unknown")}</p>}
      {items.length === 0 && <p className="text-sm text-muted-foreground">{t("tasks.none")}</p>}
      {items.map((task) => (
        <div key={task.id} className="flex items-start gap-3 rounded-md border bg-card p-3">
          <input
            className="mt-1 size-4"
            type="checkbox"
            checked={pendingId === task.id}
            disabled={pending}
            aria-label={t("tasks.complete").replace("{title}", task.title)}
            onChange={() => void complete(task.id)}
          />
          <div className="min-w-0 flex-1">
            <p className="break-words font-medium">{task.title}</p>
            {task.description && (
              <p className="whitespace-pre-wrap break-words text-sm">{task.description}</p>
            )}
            <p className="text-sm text-muted-foreground">
              {task.due_at ? vietnamTime(task.due_at) : t("tasks.noDue")}
            </p>
            {task.job_id && (
              <Link className="text-sm underline" href={`/jobs/${task.job_id}`}>
                {t("tasks.openJob")}
              </Link>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function MyTasks() {
  const [page, setPage] = useState(1);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);
  const tasks = useQuery({
    queryKey: ["tasks", page],
    queryFn: ({ signal }) =>
      api<TaskList>(`/tasks?mine=true&page=${page}&page_size=20`, { signal }),
    retry: false,
    refetchInterval: 30000,
  });
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.tasks")}
        description={t("tasks.description")}
        action={<TaskCreateDialog />}
      />
      <QueryFeedback
        pending={tasks.isPending}
        error={tasks.error}
        retry={() => {
          void tasks.refetch();
        }}
      />
      {tasks.data && !tasks.isError && (
        <>
          {tasks.data.total === 0 && <p>{t("tasks.emptyHelp")}</p>}
          {(["overdue", "today", "upcoming"] as const).map((group) => (
            <section key={group} aria-label={t(`tasks.${group}`)} className="space-y-3">
              <h2 className="text-lg font-semibold">{t(`tasks.${group}`)}</h2>
              <TaskRows items={tasks.data.items.filter((task) => taskGroup(task, now) === group)} />
            </section>
          ))}
          <div className="flex items-center gap-3">
            <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>
              {t("common.previous")}
            </Button>
            <span>{t("tasks.total").replace("{count}", String(tasks.data.total))}</span>
            <Button
              variant="outline"
              disabled={page * 20 >= tasks.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("common.next")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
