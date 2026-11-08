"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { BankCandidateCard } from "@/components/bank-candidate-card";
import { AddToJobDialog } from "@/components/bank-add-dialog";
import { BankMergeDialog } from "@/components/bank-merge-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { candidateSources, type CandidateList } from "@/lib/cv-bank-types";
import { t } from "@/i18n/vi";

const initial = { q: "", skills: "", min_years: "", location: "", source: "", semantic: false };

export function CvBank() {
  const { user } = useAuth();
  const [draft, setDraft] = useState(initial);
  const [filters, setFilters] = useState(initial);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const list = useQuery({
    queryKey: ["cv-bank", filters, page],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ page: String(page), page_size: "20" });
      for (const key of ["q", "skills", "min_years", "location", "source"] as const)
        if (filters[key]) params.set(key, filters[key]);
      return api<CandidateList>(
        `/candidates${filters.semantic ? "/search/semantic" : ""}?${params}`,
        { signal },
      );
    },
    retry: false,
  });
  const candidates = list.isError ? [] : (list.data?.items ?? []);
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.candidates")}
        description={t("bank.description")}
        action={
          <AddToJobDialog
            candidates={candidates.filter((c) => selected.includes(c.id))}
            onAdded={(ids) => setSelected((current) => current.filter((id) => !ids.includes(id)))}
          />
        }
      />
      <form
        className="space-y-4 rounded-lg border bg-card p-4"
        onSubmit={(event) => {
          event.preventDefault();
          setFilters({ ...draft });
          setPage(1);
          setSelected([]);
        }}
      >
        <label className="block space-y-2">
          <span>{t("bank.search")}</span>
          <Input
            className="h-12 text-lg"
            maxLength={200}
            value={draft.q}
            required={draft.semantic}
            onChange={(e) => setDraft({ ...draft, q: e.target.value })}
          />
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={draft.semantic}
            onChange={(e) => setDraft({ ...draft, semantic: e.target.checked })}
          />
          <span>{t("bank.semantic")}</span>
        </label>
        {draft.semantic && (
          <p className="text-sm text-muted-foreground">{t("bank.semanticHint")}</p>
        )}
        <div className="grid grid-cols-4 gap-4">
          {(["skills", "min_years", "location"] as const).map((key) => (
            <label key={key} className="space-y-2">
              <span>{t(`bank.filter.${key}`)}</span>
              <Input
                type={key === "min_years" ? "number" : "text"}
                min={key === "min_years" ? 0 : undefined}
                max={key === "min_years" ? 9999.99 : undefined}
                step={key === "min_years" ? "0.01" : undefined}
                maxLength={key === "skills" ? 1000 : 200}
                value={draft[key]}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
              />
            </label>
          ))}
          <div className="space-y-2">
            <label className="block" htmlFor="bank-source-filter">
              {t("bank.source")}
            </label>
            <select
              id="bank-source-filter"
              className="h-10 w-full rounded-md border bg-background px-3"
              value={draft.source}
              onChange={(e) => setDraft({ ...draft, source: e.target.value })}
            >
              <option value="">{t("bank.allSources")}</option>
              {candidateSources.map((source) => (
                <option key={source} value={source}>
                  {t(`bank.source.${source}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <Button type="submit">{t("bank.find")}</Button>
      </form>
      <QueryFeedback
        pending={list.isPending}
        error={list.error}
        retry={() => {
          void list.refetch();
        }}
      />
      {list.data && !list.isError && (
        <>
          <p role="status">
            {t("ranking.total")}
            {list.data.total}
          </p>
          {candidates.length === 0 && (
            <p className="rounded-lg border p-8 text-center">{t("bank.empty")}</p>
          )}
          <div className="grid grid-cols-3 gap-4">
            {candidates.map((candidate) => (
              <BankCandidateCard key={candidate.id} candidate={candidate}>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(candidate.id)}
                    onChange={(e) =>
                      setSelected((ids) =>
                        e.target.checked
                          ? [...ids, candidate.id]
                          : ids.filter((id) => id !== candidate.id),
                      )
                    }
                  />
                  <span>
                    {t("bank.select")}
                    {candidate.full_name}
                  </span>
                </label>
                {candidate.possible_duplicate && (
                  <div className="space-y-2 border-t pt-3">
                    <p className="text-sm font-medium text-amber-800">{t("bank.duplicate")}</p>
                    {user?.role === "admin" || user?.role === "lead" ? (
                      <BankMergeDialog source={candidate} target={candidate.possible_duplicate} />
                    ) : (
                      <p className="text-sm text-muted-foreground">{t("bank.askMerge")}</p>
                    )}
                  </div>
                )}
              </BankCandidateCard>
            ))}
          </div>
          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              disabled={page === 1}
              onClick={() => {
                setPage(page - 1);
                setSelected([]);
              }}
            >
              {t("users.previous")}
            </Button>
            <Button
              variant="outline"
              disabled={page * 20 >= list.data.total}
              onClick={() => {
                setPage(page + 1);
                setSelected([]);
              }}
            >
              {t("users.next")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
