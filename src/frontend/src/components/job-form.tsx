"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { jobStatuses, type Job, type JobOptions } from "@/lib/job-types";
import { t } from "@/i18n/vi";

const fieldClass =
  "w-full rounded-md border border-input bg-background p-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function JobEditor({ jobId }: { jobId?: string }) {
  const options = useQuery({
    queryKey: ["job-options"],
    queryFn: ({ signal }) => api<JobOptions>("/jobs/options", { signal }),
    retry: false,
  });
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: ({ signal }) => api<Job>(`/jobs/${jobId}`, { signal }),
    enabled: !!jobId,
    retry: false,
  });
  return (
    <div className="space-y-6">
      <PageHeader
        title={jobId ? t("jobs.editTitle") : t("jobs.create")}
        description={t("jobs.formHint")}
      />
      <QueryFeedback
        pending={options.isPending || (!!jobId && job.isPending)}
        error={options.error ?? job.error}
        retry={() => {
          void options.refetch();
          if (jobId) void job.refetch();
        }}
      />
      {options.data && (!jobId || job.data) && (
        <JobForm key={jobId ?? "new"} options={options.data} job={job.data} />
      )}
    </div>
  );
}

export function JobForm({ options, job }: { options: JobOptions; job?: Job }) {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [rescoreId, setRescoreId] = useState<string | null>(null);
  const units = [...options.hiring_units];
  if (job && !units.some((unit) => unit.id === job.hiring_unit_id))
    units.push({ id: job.hiring_unit_id, name: job.hiring_unit_name });
  const users = [...options.users];
  if (job && !users.some((person) => person.id === job.owner_id))
    users.push({ id: job.owner_id, name: job.owner_name });
  for (const id of job?.member_ids ?? [])
    if (!users.some((person) => person.id === id)) users.push({ id, name: t("jobs.inactiveUser") });
  const canAssign = user?.role === "admin" || user?.role === "lead";

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const text = (key: string) => String(data.get(key) ?? "").trim();
    const lines = (key: string) =>
      text(key)
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    const number = (key: string) => (text(key) === "" ? null : Number(text(key)));
    const title = text("title");
    const must = lines("must_have");
    const min = number("salary_min");
    const max = number("salary_max");
    const nextErrors: Record<string, string> = {};
    if (!title) nextErrors.title = t("jobs.titleRequired");
    if (!text("hiring_unit_id")) nextErrors.hiring_unit_id = t("jobs.unitRequired");
    if (text("status") === "open" && !must.length) nextErrors.must_have = t("jobs.mustRequired");
    if (
      (min !== null && (!Number.isInteger(min) || min < 0 || min > 2147483647)) ||
      (max !== null && (!Number.isInteger(max) || max < 0 || max > 2147483647)) ||
      (min !== null && max !== null && min > max)
    )
      nextErrors.salary = t("jobs.salaryInvalid");
    const headcount = number("headcount");
    if (
      headcount === null ||
      !Number.isInteger(headcount) ||
      headcount < 1 ||
      headcount > 2147483647
    )
      nextErrors.headcount = t("jobs.headcountInvalid");
    if (
      must.length > 100 ||
      lines("nice_to_have").length > 100 ||
      [...must, ...lines("nice_to_have")].some((line) => line.length > 500)
    )
      nextErrors.requirements = t("jobs.requirementsInvalid");
    setErrors(nextErrors);
    setError(null);
    if (Object.keys(nextErrors).length) {
      const firstField = nextErrors.title
        ? "title"
        : nextErrors.hiring_unit_id
          ? "hiring_unit_id"
          : nextErrors.must_have
            ? "must_have"
            : nextErrors.salary
              ? "salary_min"
              : nextErrors.headcount
                ? "headcount"
                : "must_have";
      (form.elements.namedItem(firstField) as HTMLElement | null)?.focus();
      return;
    }
    setPending(true);
    try {
      const saved = await api<Job>(job ? `/jobs/${job.id}` : "/jobs", {
        method: job ? "PATCH" : "POST",
        body: JSON.stringify({
          title,
          hiring_unit_id: text("hiring_unit_id"),
          owner_id: canAssign ? text("owner_id") : (job?.owner_id ?? user?.id),
          description: text("description"),
          must_have: must,
          nice_to_have: lines("nice_to_have"),
          location: text("location") || null,
          employment_type: text("employment_type") || null,
          salary_min: min,
          salary_max: max,
          headcount,
          deadline: text("deadline") || null,
          status: text("status"),
          member_ids: data.getAll("member_ids"),
        }),
      });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["job", saved.id] });
      toast.success(t("jobs.saved"));
      if (saved.needs_rescore) setRescoreId(saved.id);
      else router.push("/jobs");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      {units.length === 0 && (
        <p role="status" className="rounded-md border p-4">
          {t("jobs.noUnits")}{" "}
          {canAssign && (
            <Link className="underline" href="/settings">
              {t("units.title")}
            </Link>
          )}
        </p>
      )}
      <form noValidate onSubmit={save} className="rounded-lg border bg-card p-6">
        <fieldset disabled={pending || !!rescoreId} className="space-y-6">
          <div className="space-y-2">
            <label htmlFor="title">{t("jobs.title")}</label>
            <Input
              id="title"
              name="title"
              maxLength={200}
              defaultValue={job?.title}
              aria-required="true"
              aria-invalid={!!errors.title}
              aria-describedby={errors.title ? "title-error" : undefined}
            />
            {errors.title && (
              <p id="title-error" role="alert" className="text-sm text-destructive">
                {errors.title}
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <label htmlFor="hiring_unit_id">{t("jobs.unit")}</label>
              <select
                id="hiring_unit_id"
                name="hiring_unit_id"
                className={fieldClass}
                defaultValue={job?.hiring_unit_id ?? ""}
                aria-required="true"
                aria-invalid={!!errors.hiring_unit_id}
              >
                <option value="">{t("jobs.chooseUnit")}</option>
                {units.map((unit) => (
                  <option key={unit.id} value={unit.id}>
                    {unit.name}
                  </option>
                ))}
              </select>
              {errors.hiring_unit_id && (
                <p role="alert" className="text-sm text-destructive">
                  {errors.hiring_unit_id}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <label htmlFor="owner_id">{t("jobs.owner")}</label>
              <select
                id="owner_id"
                name="owner_id"
                className={fieldClass}
                defaultValue={job?.owner_id ?? user?.id}
                disabled={!canAssign}
              >
                {users.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <label htmlFor="description">{t("jobs.descriptionLabel")}</label>
            <textarea
              id="description"
              name="description"
              className={fieldClass}
              rows={4}
              maxLength={50000}
              defaultValue={job?.description}
            />
          </div>
          <div className="grid grid-cols-2 gap-6">
            {(["must_have", "nice_to_have"] as const).map((key) => (
              <div key={key} className="space-y-2">
                <label htmlFor={key}>{t(`jobs.${key}`)}</label>
                <textarea
                  id={key}
                  name={key}
                  rows={6}
                  className={fieldClass}
                  defaultValue={job?.[key].join("\n")}
                  placeholder={t("jobs.requirementExample")}
                  aria-describedby={`${key}-hint`}
                  aria-invalid={!!errors[key]}
                />
                <p id={`${key}-hint`} className="text-sm text-muted-foreground">
                  {t("jobs.requirementHint")}
                </p>
                {errors[key] && (
                  <p role="alert" className="text-sm text-destructive">
                    {errors[key]}
                  </p>
                )}
              </div>
            ))}
          </div>
          {errors.requirements && (
            <p role="alert" className="text-sm text-destructive">
              {errors.requirements}
            </p>
          )}
          <div className="grid grid-cols-2 gap-6">
            {(["location", "employment_type"] as const).map((key) => (
              <div key={key} className="space-y-2">
                <label htmlFor={key}>{t(`jobs.${key}`)}</label>
                <Input
                  id={key}
                  name={key}
                  maxLength={key === "location" ? 200 : 100}
                  defaultValue={job?.[key] ?? ""}
                />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-6">
            {(["salary_min", "salary_max"] as const).map((key) => (
              <div key={key} className="space-y-2">
                <label htmlFor={key}>{t(`jobs.${key}`)}</label>
                <Input
                  id={key}
                  name={key}
                  type="number"
                  min={0}
                  max={2147483647}
                  step={1}
                  defaultValue={job?.[key] ?? ""}
                  aria-invalid={!!errors.salary}
                />
              </div>
            ))}
          </div>
          {errors.salary && (
            <p role="alert" className="text-sm text-destructive">
              {errors.salary}
            </p>
          )}
          <div className="grid grid-cols-3 gap-6">
            <div className="space-y-2">
              <label htmlFor="headcount">{t("jobs.headcount")}</label>
              <Input
                id="headcount"
                name="headcount"
                type="number"
                min={1}
                max={2147483647}
                step={1}
                defaultValue={job?.headcount ?? 1}
                aria-invalid={!!errors.headcount}
              />
              {errors.headcount && (
                <p role="alert" className="text-sm text-destructive">
                  {errors.headcount}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <label htmlFor="deadline">{t("jobs.deadline")}</label>
              <Input id="deadline" name="deadline" type="date" defaultValue={job?.deadline ?? ""} />
            </div>
            <div className="space-y-2">
              <label htmlFor="status">{t("jobs.status")}</label>
              <select
                id="status"
                name="status"
                className={fieldClass}
                defaultValue={job?.status ?? "draft"}
              >
                {jobStatuses.map((status) => (
                  <option value={status} key={status}>
                    {t(`jobs.${status}`)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <fieldset className="space-y-3">
            <legend className="mb-2">{t("jobs.members")}</legend>
            <div className="grid max-h-52 grid-cols-3 gap-3 overflow-auto rounded-md border p-3">
              {users.map((person) => (
                <label key={person.id} className="flex min-w-0 items-center gap-2">
                  <input
                    type="checkbox"
                    name="member_ids"
                    value={person.id}
                    defaultChecked={job?.member_ids.includes(person.id)}
                  />
                  <span className="truncate" title={person.name}>
                    {person.name}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              disabled={pending || !!rescoreId}
              onClick={() => router.push("/jobs")}
            >
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={pending || !!rescoreId || units.length === 0}>
              {pending ? t("common.processing") : t("jobs.save")}
            </Button>
          </div>
        </fieldset>
      </form>
      <ConfirmDialog
        open={!!rescoreId}
        title={t("jobs.rescoreTitle")}
        description={t("jobs.rescoreDescription")}
        confirmLabel={t("jobs.rescoreConfirm")}
        onOpenChange={(open) => {
          if (!open) {
            setRescoreId(null);
            router.push("/jobs");
          }
        }}
        onConfirm={async () => {
          await api(`/jobs/${rescoreId}/rescore`, { method: "POST" });
          toast.success(t("jobs.rescoreQueued"));
        }}
      />
    </>
  );
}
