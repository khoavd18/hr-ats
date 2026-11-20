"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ConsentDialog } from "@/components/consent-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { Candidate } from "@/lib/profile-types";
import { t } from "@/i18n/vi";

const fields = [
  "full_name",
  "email",
  "phone",
  "location",
  "current_title",
  "years_experience",
  "skills",
] as const;
const labels = {
  full_name: "profile.name",
  email: "profile.email",
  phone: "profile.phone",
  location: "profile.location",
  current_title: "profile.title",
  years_experience: "profile.years",
  skills: "profile.skills",
} as const;

export function ProfileInfo({
  candidate,
  onSaved,
}: {
  candidate: Candidate;
  onSaved: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api(`/candidates/${candidate.id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: async () => {
      setEditing(false);
      await onSaved();
    },
  });
  return (
    <section className="space-y-3" aria-label={t("profile.info")}>
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{t("profile.info")}</h2>
        {!editing && (
          <Button
            variant="outline"
            onClick={() => {
              save.reset();
              setEditing(true);
            }}
          >
            {t("profile.edit")}
          </Button>
        )}
      </div>
      {!candidate.consent_at && (
        <p className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {t("profile.noConsent")}
        </p>
      )}
      <ConsentDialog candidateId={candidate.id} onSaved={onSaved} />
      {save.isSuccess && <p role="status">{t("profile.saved")}</p>}
      {editing ? (
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            const body: Record<string, unknown> = {};
            fields.forEach((field) => {
              const value = String(data.get(field) ?? "").trim();
              body[field] =
                field === "skills"
                  ? value
                      .split(",")
                      .map((v) => v.trim())
                      .filter(Boolean)
                  : value || null;
            });
            save.mutate(body);
          }}
        >
          <fieldset disabled={save.isPending} className="space-y-3">
            {fields.map((field) => (
              <div key={field} className="space-y-1">
                <label htmlFor={`profile-${field}`}>{t(labels[field])}</label>
                <Input
                  id={`profile-${field}`}
                  name={field}
                  required={field === "full_name"}
                  type={
                    field === "email" ? "email" : field === "years_experience" ? "number" : "text"
                  }
                  min={field === "years_experience" ? "0" : undefined}
                  max={field === "years_experience" ? "9999.99" : undefined}
                  step={field === "years_experience" ? "0.01" : undefined}
                  maxLength={
                    field === "email"
                      ? 254
                      : field === "phone"
                        ? 50
                        : field === "skills"
                          ? undefined
                          : 200
                  }
                  defaultValue={
                    field === "skills" ? candidate.skills.join(", ") : (candidate[field] ?? "")
                  }
                />
              </div>
            ))}
            {save.isError && (
              <p role="alert">
                {save.error instanceof ApiError ? save.error.message : t("api.unknown")}
              </p>
            )}
            <div className="flex gap-2">
              <Button type="submit">
                {t(save.isPending ? "common.processing" : "profile.save")}
              </Button>
              <Button type="button" variant="outline" onClick={() => setEditing(false)}>
                {t("common.cancel")}
              </Button>
            </div>
          </fieldset>
        </form>
      ) : (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          {fields.map((field) => (
            <div key={field} className="contents">
              <dt className="text-muted-foreground">
                {field === "skills" ? t("ranking.skills") : t(labels[field])}
              </dt>
              <dd className="min-w-0 break-words">
                {field === "skills"
                  ? candidate.skills.join(", ") || t("ranking.unknown")
                  : (candidate[field] ?? t("ranking.unknown"))}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
