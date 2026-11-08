"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AiLevelBadge, type AiLevel } from "@/components/ai-level-badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { aiLevels } from "@/lib/ranking-types";
import type { ApplicationDetail, Feedback } from "@/lib/profile-types";
import { t, vi, type TranslationKey } from "@/i18n/vi";

function flagLabel(flag: string) {
  const key = `profile.flag.${flag}` as TranslationKey;
  return Object.hasOwn(vi, key) ? t(key) : t("profile.flag.other");
}

export function ProfileAI({
  detail,
  onSaved,
}: {
  detail: ApplicationDetail;
  onSaved: () => Promise<void>;
}) {
  const [disagreeing, setDisagreeing] = useState(false);
  const assessment = detail.application;
  const save = useMutation({
    mutationFn: (body: Feedback) =>
      api(`/applications/${assessment.id}/ai-feedback`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: async () => {
      setDisagreeing(false);
      await onSaved();
    },
  });
  return (
    <section aria-label={t("profile.ai")} className="space-y-3 border-t pt-5">
      <h2 className="font-semibold">{t("profile.ai")}</h2>
      <p className="text-sm text-muted-foreground">{t("profile.aiHint")}</p>
      {assessment.ai_status !== "done" ? (
        <p role="status">
          {t(assessment.ai_status === "failed" ? "ranking.aiFailed" : "upload.scoring")}
        </p>
      ) : (
        <>
          {assessment.ai_level && <AiLevelBadge level={assessment.ai_level} />}
          {assessment.ai_level === "insufficient" && (
            <p className="rounded-md bg-muted p-3">{t("profile.insufficient")}</p>
          )}
          {assessment.ai_score !== null && (
            <p className="text-sm">
              {t("profile.score")}
              {assessment.ai_score}
            </p>
          )}
          <ul className="list-inside list-disc space-y-1 text-sm">
            {assessment.ai_reasons.slice(0, 3).map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
          {assessment.ai_criteria.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("profile.criterion")}</TableHead>
                  <TableHead>{t("profile.result")}</TableHead>
                  <TableHead>{t("profile.evidence")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {assessment.ai_criteria.map((criterion, index) => (
                  <TableRow key={index}>
                    <TableCell className="min-w-28 whitespace-normal">
                      <p className="break-words">{criterion.criterion}</p>
                      <span className="text-xs text-muted-foreground">
                        {t(criterion.kind === "must" ? "profile.must" : "profile.nice")}
                      </span>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {t(`profile.${criterion.result}`)}
                    </TableCell>
                    <TableCell className="min-w-28 whitespace-normal">
                      <blockquote className="break-words text-sm">
                        {criterion.evidence || t("profile.noEvidence")}
                      </blockquote>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p>{t("profile.noCriteria")}</p>
          )}
          {assessment.ai_flags.length > 0 && (
            <ul className="space-y-1 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              {assessment.ai_flags.map((flag, index) => (
                <li key={index}>{flagLabel(flag)}</li>
              ))}
            </ul>
          )}
          {detail.feedback && (
            <div className="space-y-1 text-sm">
              <p>
                {t("profile.yourFeedback")}
                {t(detail.feedback.verdict === "agree" ? "profile.agree" : "profile.disagree")}
              </p>
              {detail.feedback.corrected_level && (
                <AiLevelBadge level={detail.feedback.corrected_level} />
              )}
              {detail.feedback.comment && (
                <p className="whitespace-pre-wrap break-words">{detail.feedback.comment}</p>
              )}
            </div>
          )}
          {save.isSuccess && <p role="status">{t("profile.feedbackSaved")}</p>}
          {save.isError && (
            <p role="alert">
              {save.error instanceof ApiError ? save.error.message : t("api.unknown")}
            </p>
          )}
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={save.isPending}
              onClick={() =>
                save.mutate({ verdict: "agree", corrected_level: null, comment: null })
              }
            >
              {t("profile.agree")}
            </Button>
            <Button
              variant="outline"
              disabled={save.isPending}
              onClick={() => {
                save.reset();
                setDisagreeing(true);
              }}
            >
              {t("profile.disagree")}
            </Button>
          </div>
          {disagreeing && (
            <form
              className="space-y-3 rounded-md border p-3"
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                save.mutate({
                  verdict: "disagree",
                  corrected_level: data.get("level") as AiLevel,
                  comment: String(data.get("comment") ?? "").trim() || null,
                });
              }}
            >
              <fieldset disabled={save.isPending} className="space-y-3">
                <label className="block space-y-1">
                  <span>{t("profile.corrected")}</span>
                  <select
                    name="level"
                    required
                    defaultValue={detail.feedback?.corrected_level ?? ""}
                    className="block h-10 w-full rounded-md border bg-background px-3"
                  >
                    <option value="" disabled>
                      {t("profile.corrected")}
                    </option>
                    {aiLevels.map((level) => (
                      <option key={level} value={level}>
                        {t(`ai.${level}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block space-y-1">
                  <span>{t("profile.comment")}</span>
                  <textarea
                    name="comment"
                    maxLength={10000}
                    defaultValue={detail.feedback?.comment ?? ""}
                    className="min-h-20 w-full rounded-md border bg-background p-2"
                  />
                </label>
                <div className="flex gap-2">
                  <Button type="submit">
                    {t(save.isPending ? "common.processing" : "profile.sendFeedback")}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setDisagreeing(false)}>
                    {t("common.cancel")}
                  </Button>
                </div>
              </fieldset>
            </form>
          )}
        </>
      )}
    </section>
  );
}
