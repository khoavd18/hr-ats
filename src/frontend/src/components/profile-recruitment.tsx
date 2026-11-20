"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { Interview, Offer, Placement, RecruitmentRecords } from "@/lib/recruitment-types";
import type { Stage } from "@/lib/ranking-types";
import { t } from "@/i18n/vi";

type Save = (path: string, body: object, target?: Stage) => Promise<boolean>;
const selectClass = "h-10 w-full rounded-md border bg-background px-2";
const textClass = "min-h-20 w-full rounded-md border bg-background p-2";
const optional = (data: FormData, key: string) => String(data.get(key) ?? "").trim() || null;
const money = (data: FormData, key: string) =>
  optional(data, key) === null ? null : Number(data.get(key));

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1 text-sm">
      <span>{label}</span>
      {children}
    </label>
  );
}

function InterviewForm({
  applicationId,
  save,
  busy,
  allowed,
}: {
  applicationId: string;
  save: Save;
  busy: boolean;
  allowed: boolean;
}) {
  return (
    <form
      aria-label={t("recruitment.schedule")}
      onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = new FormData(form);
        const ok = await save(
          `/applications/${applicationId}/interviews`,
          {
            round: Number(data.get("round")),
            // HR enters wall time in Vietnam; browser/OS timezone does not change it.
            scheduled_at: `${data.get("scheduled_at")}:00+07:00`,
            duration_minutes: Number(data.get("duration_minutes")),
            location_or_link: optional(data, "location_or_link"),
            interviewers: String(data.get("interviewers") ?? "")
              .split("\n")
              .map((v) => v.trim())
              .filter(Boolean),
          },
          "interview",
        );
        if (ok) form.reset();
      }}
    >
      <fieldset disabled={busy || !allowed} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("recruitment.round")}>
            <Input name="round" type="number" min={1} max={2147483647} defaultValue={1} required />
          </Field>
          <Field label={t("recruitment.duration")}>
            <Input
              name="duration_minutes"
              type="number"
              min={1}
              max={1440}
              defaultValue={60}
              required
            />
          </Field>
        </div>
        <Field label={t("recruitment.scheduledAt")}>
          <Input name="scheduled_at" type="datetime-local" required />
        </Field>
        <Field label={t("recruitment.location")}>
          <Input name="location_or_link" maxLength={10000} />
        </Field>
        <Field label={t("recruitment.interviewers")}>
          <textarea name="interviewers" className={textClass} />
        </Field>
        <Button type="submit">{t(busy ? "common.processing" : "recruitment.schedule")}</Button>
      </fieldset>
      {!allowed && (
        <p className="mt-2 text-sm text-muted-foreground">{t("recruitment.interviewStageHint")}</p>
      )}
    </form>
  );
}

function InterviewResult({
  row,
  save,
  busy,
  download,
}: {
  row: Interview;
  save: Save;
  busy: boolean;
  download: (id: string) => void;
}) {
  return (
    <article className="space-y-3 rounded-md border p-3">
      <h3 className="font-medium">
        {t("recruitment.round")} {row.round}
      </h3>
      <p>
        <time dateTime={row.scheduled_at}>
          {new Intl.DateTimeFormat("vi-VN", {
            dateStyle: "short",
            timeStyle: "short",
            timeZone: "Asia/Ho_Chi_Minh",
          }).format(new Date(row.scheduled_at))}
        </time>
        {t("common.separator")}
        {row.duration_minutes} {t("recruitment.minutes")}
      </p>
      {row.location_or_link && (
        <p className="whitespace-pre-wrap break-words">{row.location_or_link}</p>
      )}
      <p className="break-words">{row.interviewers.join(t("common.separator"))}</p>
      <Button type="button" variant="outline" disabled={busy} onClick={() => download(row.id)}>
        {t("recruitment.downloadIcs")}
      </Button>
      <form
        aria-label={`${t("recruitment.resultForm")} ${row.round}`}
        onSubmit={async (event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          await save(`/interviews/${row.id}`, {
            result: data.get("result"),
            feedback: optional(data, "feedback"),
          });
        }}
      >
        <fieldset disabled={busy} className="space-y-3">
          <Field label={t("recruitment.result")}>
            <select name="result" className={selectClass} defaultValue={row.result}>
              {(["pending", "pass", "fail", "no_show"] as const).map((value) => (
                <option key={value} value={value}>
                  {t(`recruitment.result.${value}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("recruitment.feedback")}>
            <textarea
              name="feedback"
              maxLength={10000}
              className={textClass}
              defaultValue={row.feedback ?? ""}
            />
          </Field>
          <Button type="submit" variant="outline">
            {t("recruitment.saveResult")}
          </Button>
        </fieldset>
      </form>
    </article>
  );
}

function OfferForm({
  row,
  applicationId,
  save,
  busy,
}: {
  row?: Offer;
  applicationId: string;
  save: Save;
  busy: boolean;
}) {
  const statuses =
    row?.status === "sent"
      ? (["sent", "accepted", "declined"] as const)
      : row?.status === "accepted" || row?.status === "declined"
        ? [row.status]
        : (["draft", "sent"] as const);
  return (
    <form
      aria-label={t(row ? "recruitment.editOffer" : "recruitment.createOffer")}
      className="rounded-md border p-3"
      onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = new FormData(form);
        const status = data.get("status");
        const ok = await save(
          row ? `/offers/${row.id}` : `/applications/${applicationId}/offers`,
          {
            salary: money(data, "salary"),
            start_date: optional(data, "start_date"),
            status,
            notes: optional(data, "notes"),
          },
          status === "sent" && (!row || row.status === "draft") ? "offer" : undefined,
        );
        if (ok && !row) form.reset();
      }}
    >
      <fieldset disabled={busy} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("recruitment.salary")}>
            <Input
              name="salary"
              type="number"
              min={0}
              max={2147483647}
              defaultValue={row?.salary ?? ""}
            />
          </Field>
          <Field label={t("recruitment.startDate")}>
            <Input name="start_date" type="date" defaultValue={row?.start_date ?? ""} />
          </Field>
        </div>
        <Field label={t("recruitment.offerStatus")}>
          <select name="status" className={selectClass} defaultValue={row?.status ?? "draft"}>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {t(`recruitment.offer.${value}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("recruitment.notes")}>
          <textarea
            name="notes"
            className={textClass}
            maxLength={10000}
            defaultValue={row?.notes ?? ""}
          />
        </Field>
        <Button type="submit" variant={row ? "outline" : "default"}>
          {t(row ? "recruitment.saveOffer" : "recruitment.createOffer")}
        </Button>
      </fieldset>
    </form>
  );
}

function PlacementForm({
  row,
  applicationId,
  save,
  busy,
  allowed,
}: {
  row: Placement | null;
  applicationId: string;
  save: Save;
  busy: boolean;
  allowed: boolean;
}) {
  return (
    <form
      aria-label={t("recruitment.placement")}
      onSubmit={async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        await save(
          row ? `/placements/${row.id}` : `/applications/${applicationId}/placement`,
          {
            start_date: data.get("start_date"),
            fee_amount: money(data, "fee_amount"),
            guarantee_until: optional(data, "guarantee_until"),
            ...(row ? { status: data.get("status") } : {}),
          },
          row ? undefined : "hired",
        );
      }}
    >
      <fieldset disabled={busy || (!row && !allowed)} className="space-y-3">
        <Field label={t("recruitment.startDate")}>
          <Input name="start_date" type="date" required defaultValue={row?.start_date ?? ""} />
        </Field>
        <Field label={t("recruitment.fee")}>
          <Input
            name="fee_amount"
            type="number"
            min={0}
            max={2147483647}
            defaultValue={row?.fee_amount ?? ""}
          />
        </Field>
        <Field label={t("recruitment.guarantee")}>
          <Input name="guarantee_until" type="date" defaultValue={row?.guarantee_until ?? ""} />
        </Field>
        {row && (
          <Field label={t("recruitment.placementStatus")}>
            <select name="status" className={selectClass} defaultValue={row.status}>
              {(["active", "left_in_guarantee", "completed"] as const).map((value) => (
                <option key={value} value={value}>
                  {t(`recruitment.placement.${value}`)}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Button type="submit">
          {t(row ? "recruitment.savePlacement" : "recruitment.placement")}
        </Button>
      </fieldset>
      {!row && !allowed && (
        <p className="mt-2 text-sm text-muted-foreground">{t("recruitment.placementStageHint")}</p>
      )}
    </form>
  );
}

export function ProfileRecruitment({
  applicationId,
  stage,
  records,
}: {
  applicationId: string;
  stage: Stage;
  records: RecruitmentRecords;
}) {
  const client = useQueryClient();
  const mounted = useRef(true);
  const locked = useRef(false);
  const notice = useRef<string | number | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canUndo, setCanUndo] = useState(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (notice.current !== undefined) toast.dismiss(notice.current);
    };
  }, []);
  async function refresh() {
    await Promise.all(
      [
        ["application-profile", applicationId],
        ["job-ranking"],
        ["job-pipeline"],
        ["jobs"],
        ["interviews"],
      ].map((queryKey) => client.invalidateQueries({ queryKey })),
    );
  }
  async function undo() {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError(null);
    try {
      await api(`/applications/${applicationId}/undo`, { method: "POST" });
      if (!mounted.current) return;
      await refresh();
      if (!mounted.current) return;
      setCanUndo(false);
      if (notice.current !== undefined) toast.dismiss(notice.current);
      toast.success(t("pipeline.undone"));
    } catch (err) {
      if (mounted.current) setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  const save: Save = async (path, body, target) => {
    if (locked.current) return false;
    locked.current = true;
    setBusy(true);
    setError(null);
    try {
      await api(path, {
        method: path.startsWith("/applications/") ? "POST" : "PATCH",
        body: JSON.stringify(body),
      });
      if (!mounted.current) return false;
      await refresh();
      if (!mounted.current) return false;
      if (notice.current !== undefined) toast.dismiss(notice.current);
      if (target && stage !== target) setCanUndo(true);
      notice.current = toast.success(
        t("recruitment.saved"),
        target && stage !== target
          ? {
              description: t("recruitment.undoHint"),
              action: {
                label: t("pipeline.undo"),
                onClick: () => {
                  void undo();
                },
              },
            }
          : undefined,
      );
      return true;
    } catch (err) {
      if (mounted.current) setError(err instanceof ApiError ? err.message : t("api.unknown"));
      return false;
    } finally {
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  async function download(id: string) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError(null);
    try {
      const blob = await api<Blob>(`/interviews/${id}/ics`, { responseType: "blob" });
      if (!mounted.current) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `interview-${id}.ics`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (err) {
      if (mounted.current) setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <section aria-label={t("recruitment.title")} className="space-y-5 border-t pt-5">
      <h2 className="font-semibold">{t("recruitment.title")}</h2>
      {error && <p role="alert">{error}</p>}
      {canUndo && (
        <div className="space-y-2 rounded-md border p-3 text-sm" role="status">
          <p>{t("recruitment.undoHint")}</p>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => {
              void undo();
            }}
          >
            {t("pipeline.undo")}
          </Button>
        </div>
      )}
      <section aria-label={t("recruitment.interviews")} className="space-y-3">
        <h3 className="font-medium">{t("recruitment.interviews")}</h3>
        <p className="text-sm text-muted-foreground">{t("recruitment.timezone")}</p>
        {records.interviews.length === 0 && <p>{t("recruitment.noInterviews")}</p>}
        {records.interviews.map((row) => (
          <InterviewResult
            key={`${row.id}-${row.updated_at}`}
            row={row}
            save={save}
            busy={busy}
            download={(id) => {
              void download(id);
            }}
          />
        ))}
        <InterviewForm
          applicationId={applicationId}
          save={save}
          busy={busy}
          allowed={["submitted", "interview"].includes(stage)}
        />
      </section>
      <section aria-label={t("recruitment.offers")} className="space-y-3">
        <h3 className="font-medium">{t("recruitment.offers")}</h3>
        <p className="text-sm text-muted-foreground">{t("recruitment.offerNotice")}</p>
        {records.offers.length === 0 && <p>{t("recruitment.noOffers")}</p>}
        {records.offers.map((row) => (
          <OfferForm
            key={`${row.id}-${row.updated_at}`}
            row={row}
            applicationId={applicationId}
            save={save}
            busy={busy}
          />
        ))}
        <OfferForm applicationId={applicationId} save={save} busy={busy} />
      </section>
      <section aria-label={t("recruitment.placement")} className="space-y-3">
        <h3 className="font-medium">{t("recruitment.placement")}</h3>
        <PlacementForm
          key={
            records.placement ? `${records.placement.id}-${records.placement.updated_at}` : "new"
          }
          row={records.placement}
          applicationId={applicationId}
          save={save}
          busy={busy}
          allowed={["offer", "hired"].includes(stage)}
        />
      </section>
    </section>
  );
}
