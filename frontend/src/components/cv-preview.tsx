"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ProfileFile } from "@/lib/profile-types";
import { t } from "@/i18n/vi";

export function CvPreview({ file }: { file: ProfileFile }) {
  const docx =
    file.mime_type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const [url, setUrl] = useState<string | null>(null);
  const download = useQuery({
    queryKey: ["profile-cv", file.id],
    queryFn: ({ signal }) =>
      api<Blob>(`/cv-files/${file.id}/download`, { signal, responseType: "blob" }),
    enabled: !docx,
    retry: false,
    gcTime: 0,
  });
  useEffect(() => {
    if (!download.data) return;
    // Only validated server MIME types may enter an active browser viewer.
    if (!["application/pdf", "image/png", "image/jpeg"].includes(file.mime_type)) return;
    const next = URL.createObjectURL(new Blob([download.data], { type: file.mime_type }));
    setUrl(next);
    return () => {
      URL.revokeObjectURL(next);
    };
  }, [download.data, file.mime_type]);
  if (docx)
    return (
      <pre className="max-h-[75vh] overflow-auto whitespace-pre-wrap break-words rounded-md border bg-muted/30 p-4 font-sans text-sm">
        {file.extracted_text || t("profile.noText")}
      </pre>
    );
  return (
    <div className="space-y-3">
      <QueryFeedback
        pending={download.isPending}
        error={download.error}
        retry={() => {
          void download.refetch();
        }}
      />
      {url && !download.isError && (
        <>
          {file.mime_type === "application/pdf" ? (
            <iframe
              src={url}
              title={t("profile.cv")}
              className="h-[70vh] w-full rounded-md border"
            />
          ) : (
            // Native image preserves authenticated blob URLs; no external optimizer request.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt={t("profile.cv")} className="max-h-[70vh] w-full object-contain" />
          )}
          <Button asChild variant="outline">
            <a
              href={url}
              download={`cv-${file.id}.${file.mime_type === "application/pdf" ? "pdf" : file.mime_type === "image/png" ? "png" : "jpg"}`}
            >
              {t("profile.download")}
            </a>
          </Button>
        </>
      )}
    </div>
  );
}
