"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { t, type TranslationKey } from "@/i18n/vi";
import type { CvFile, CvFileStatus, UploadResponse } from "@/lib/ranking-types";

type UploadRow = {
  key: number;
  name: string;
  file?: CvFile;
  error?: TranslationKey;
  duplicate?: boolean;
};
const uploadErrors: Record<string, TranslationKey> = {
  INVALID_FILE_TYPE: "upload.invalidType",
  FILE_TOO_LARGE: "upload.tooLarge",
  MACRO_NOT_ALLOWED: "upload.macro",
  FORBIDDEN: "api.forbidden",
  NOT_FOUND: "api.notFound",
  STORAGE_UNAVAILABLE: "api.unavailable",
  CV_PROCESSING_FAILED: "upload.readFailed",
};

function isFinished(file: CvFileStatus) {
  return (
    file.status === "failed" ||
    (file.status === "done" &&
      (file.ai_status === null || file.ai_status === "done" || file.ai_status === "failed"))
  );
}

export function CvUpload({ jobId }: { jobId: string }) {
  const [rows, setRows] = useState<UploadRow[]>([]);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const nextKey = useRef(0);
  const client = useQueryClient();
  const files = [
    ...new Map(
      rows.filter((row) => row.file?.job_id === jobId).map((row) => [row.file!.id, row.file!]),
    ).values(),
  ];
  const queries = useQueries({
    queries: files.map((file) => ({
      queryKey: ["cv-file-status", file.id],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api<CvFileStatus>(`/cv-files/${file.id}`, { signal }),
      retry: false,
      refetchInterval: (query: { state: { data?: CvFileStatus; error: unknown } }) =>
        query.state.error || (query.state.data && isFinished(query.state.data)) ? false : 3000,
    })),
  });
  const statusVersion = queries
    .map((query) => `${query.data?.status}:${query.data?.ai_status}`)
    .join("|");
  useEffect(() => {
    void client.invalidateQueries({ queryKey: ["job-ranking", jobId] });
    void client.invalidateQueries({ queryKey: ["jobs"] });
  }, [statusVersion, client, jobId]);

  const upload = useMutation({
    mutationFn: async ({ selected }: { selected: File[]; added: UploadRow[] }) => {
      const body = new FormData();
      body.append("job_id", jobId);
      selected.forEach((file) => body.append("files", file));
      return api<UploadResponse>("/cv-files", { method: "POST", body });
    },
    onSuccess: (result, { added }) => {
      setRows((current) =>
        current.map((row) => {
          const index = added.findIndex((item) => item.key === row.key);
          if (index < 0) return row;
          const item = result.items.find((item) => item.index === index);
          if (!item || (!item.cv_file && !item.error))
            return { ...row, error: "api.invalidResponse" };
          return {
            ...row,
            file: item.cv_file ?? undefined,
            duplicate: item.duplicate,
            error: item.error ? (uploadErrors[item.error.code] ?? "upload.failed") : undefined,
          };
        }),
      );
      // A SHA duplicate can have the same ID as a previous completed attempt.
      void client.invalidateQueries({ queryKey: ["cv-file-status"] });
      void client.invalidateQueries({ queryKey: ["job-ranking", jobId] });
    },
    onError: (error, { added }) =>
      setRows((current) =>
        current.map((row) =>
          added.some((item) => item.key === row.key)
            ? {
                ...row,
                error:
                  error instanceof ApiError && error.status === 429
                    ? "api.rateLimit"
                    : error instanceof ApiError && error.status === 413
                      ? "upload.batchTooLarge"
                      : "upload.failed",
              }
            : row,
        ),
      ),
  });

  function addFiles(selected: File[]) {
    if (!selected.length || upload.isPending) return;
    const added: UploadRow[] = selected.map((file) => ({
      key: nextKey.current++,
      name: file.name,
      ...(selected.length > 50 ? { error: "upload.tooMany" as const } : {}),
    }));
    setRows((current) => [...current, ...added]);
    if (selected.length <= 50) upload.mutate({ selected, added });
  }

  return (
    <section className="space-y-3" aria-label={t("upload.title")}>
      <div
        className={`rounded-lg border-2 border-dashed p-6 text-center ${dragging ? "border-primary bg-muted" : "border-border"}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          addFiles(Array.from(event.dataTransfer.files));
        }}
        aria-busy={upload.isPending}
      >
        <p className="mb-2 font-medium">{t("upload.drop")}</p>
        <p className="mb-4 text-sm text-muted-foreground">{t("upload.help")}</p>
        <input
          ref={input}
          type="file"
          multiple
          accept=".pdf,.docx,.jpg,.jpeg,.png"
          className="sr-only"
          aria-label={t("upload.title")}
          disabled={upload.isPending}
          onChange={(event) => {
            addFiles(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        <Button disabled={upload.isPending} onClick={() => input.current?.click()}>
          {t("upload.title")}
        </Button>
      </div>
      {rows.length > 0 && (
        <ul
          className="divide-y rounded-lg border bg-card"
          aria-label={t("upload.progress")}
          aria-live="polite"
        >
          {rows.map((row) => {
            const index = files.findIndex((file) => file.id === row.file?.id);
            const query = queries[index];
            const data = query?.data;
            let message: TranslationKey = "upload.uploading";
            let failed = false;
            if (row.error) {
              message = row.error;
              failed = true;
            } else if (row.file?.job_id !== jobId && row.file) message = "upload.duplicateOther";
            else if (query?.error) {
              message = "upload.statusFailed";
              failed = true;
            } else if ((data?.status ?? row.file?.status) === "failed") {
              message = "upload.readFailed";
              failed = true;
            } else if (data?.status === "done") {
              if (data.ai_status === "failed") {
                message = "upload.aiFailed";
                failed = true;
              } else if (data.ai_status === "done") message = "upload.done";
              else if (data.ai_status === null) {
                message = "upload.noApplication";
                failed = true;
              } else message = "upload.scoring";
            } else if (row.file) message = "upload.reading";
            return (
              <li key={row.key} className="flex items-center justify-between gap-4 p-3">
                <span className="min-w-0 flex-1 truncate" title={row.name}>
                  {row.name}
                </span>
                <span
                  className={failed ? "text-sm text-destructive" : "text-sm text-muted-foreground"}
                  role={failed ? "alert" : "status"}
                >
                  {t(message)}
                </span>
                {row.duplicate && (
                  <span className="text-xs text-muted-foreground">{t("upload.duplicate")}</span>
                )}
                {query?.error && !row.error && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      void query.refetch();
                    }}
                  >
                    {t("common.retry")}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
