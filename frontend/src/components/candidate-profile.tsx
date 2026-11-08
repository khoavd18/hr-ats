"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CvPreview } from "@/components/cv-preview";
import { ProfileInfo } from "@/components/profile-info";
import { ProfileAI } from "@/components/profile-ai";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { ApplicationDetail, ProfileActivity } from "@/lib/profile-types";
import { t, vi, type TranslationKey } from "@/i18n/vi";

function activityLabel(type: string) {
  const key = `profile.activity.${type}` as TranslationKey;
  return Object.hasOwn(vi, key) ? t(key) : t("profile.activity.other");
}

function History({ activities }: { activities: ProfileActivity[] }) {
  return (
    <section aria-label={t("profile.history")} className="space-y-3 border-t pt-5">
      <h2 className="font-semibold">{t("profile.history")}</h2>
      {activities.length === 0 ? (
        <p>{t("profile.noHistory")}</p>
      ) : (
        <ol className="space-y-3">
          {activities.map((activity) => (
            <li key={activity.id} className="space-y-1 rounded-md border p-3 text-sm">
              <p className="font-medium">{activityLabel(activity.type)}</p>
              <p className="text-xs text-muted-foreground">
                {activity.actor_name ?? t("profile.system")}
                {t("common.separator")}
                <time dateTime={activity.occurred_at}>
                  {new Intl.DateTimeFormat("vi-VN", {
                    dateStyle: "short",
                    timeStyle: "short",
                    timeZone: "Asia/Ho_Chi_Minh",
                  }).format(new Date(activity.occurred_at))}
                </time>
              </p>
              {activity.type === "note" && typeof activity.payload.text === "string" && (
                <p className="whitespace-pre-wrap break-words">{activity.payload.text}</p>
              )}
              {activity.type === "ai_feedback" &&
                (activity.payload.verdict === "agree" ||
                  activity.payload.verdict === "disagree") && (
                  <p>
                    {t(activity.payload.verdict === "agree" ? "profile.agree" : "profile.disagree")}
                  </p>
                )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function CandidateProfile({ applicationId }: { applicationId: string }) {
  const queryClient = useQueryClient();
  const [fileId, setFileId] = useState("");
  const [note, setNote] = useState("");
  const detail = useQuery({
    queryKey: ["application-profile", applicationId],
    queryFn: ({ signal }) => api<ApplicationDetail>(`/applications/${applicationId}`, { signal }),
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      !query.state.error &&
      query.state.data &&
      ["pending", "running"].includes(query.state.data.application.ai_status)
        ? 3000
        : false,
  });
  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["application-profile", applicationId] }),
      queryClient.invalidateQueries({ queryKey: ["job-ranking"] }),
    ]);
  }
  const addNote = useMutation({
    mutationFn: () =>
      api(`/applications/${applicationId}/notes`, {
        method: "POST",
        body: JSON.stringify({ text: note.trim() }),
      }),
    onSuccess: async () => {
      setNote("");
      await refresh();
    },
  });
  const file = detail.data?.cv_files.find((f) => f.id === fileId) ?? detail.data?.cv_files[0];
  return (
    <div className="mt-5">
      <QueryFeedback
        pending={detail.isPending}
        error={detail.error}
        retry={() => {
          void detail.refetch();
        }}
      />
      {detail.data && !detail.isError && (
        <div className="grid grid-cols-2 items-start gap-6">
          <section aria-label={t("profile.cv")} className="sticky top-0 min-w-0 space-y-3">
            <h2 className="font-semibold">{t("profile.cv")}</h2>
            {detail.data.cv_files.length > 1 && (
              <label className="block space-y-1">
                <span>{t("profile.file")}</span>
                <select
                  className="h-10 w-full rounded-md border bg-background px-3"
                  value={file?.id ?? ""}
                  onChange={(event) => setFileId(event.target.value)}
                >
                  {detail.data.cv_files.map((item, index) => (
                    <option key={item.id} value={item.id}>
                      {`${t("profile.file")} ${index + 1}`}
                      {t("common.separator")}
                      {item.mime_type === "application/pdf"
                        ? t("profile.pdf")
                        : item.mime_type.startsWith("image/")
                          ? t("profile.image")
                          : t("profile.document")}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {file ? <CvPreview key={file.id} file={file} /> : <p>{t("profile.noCv")}</p>}
          </section>
          <div className="min-w-0 space-y-5">
            <ProfileInfo candidate={detail.data.candidate} onSaved={refresh} />
            <ProfileAI detail={detail.data} onSaved={refresh} />
            <History activities={detail.data.activities} />
            <form
              className="space-y-3 border-t pt-5"
              onSubmit={(event) => {
                event.preventDefault();
                if (note.trim()) addNote.mutate();
              }}
            >
              <label className="block space-y-2">
                <span className="font-semibold">{t("profile.note")}</span>
                <textarea
                  required
                  maxLength={10000}
                  className="min-h-24 w-full rounded-md border bg-background p-2"
                  value={note}
                  disabled={addNote.isPending}
                  onChange={(event) => {
                    setNote(event.target.value);
                    addNote.reset();
                  }}
                />
              </label>
              {addNote.isError && (
                <p role="alert">
                  {addNote.error instanceof ApiError ? addNote.error.message : t("api.unknown")}
                </p>
              )}
              {addNote.isSuccess && <p role="status">{t("profile.noteSaved")}</p>}
              <Button type="submit" disabled={addNote.isPending || !note.trim()}>
                {t(addNote.isPending ? "common.processing" : "profile.sendNote")}
              </Button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
