"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BankCandidateCard } from "@/components/bank-candidate-card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import type { CandidateBrief } from "@/lib/cv-bank-types";
import { t } from "@/i18n/vi";

export function BankMergeDialog({
  source,
  target,
}: {
  source: CandidateBrief;
  target: CandidateBrief;
}) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [keepId, setKeepId] = useState(target.id);
  const cancel = useRef<HTMLButtonElement>(null);
  async function merge() {
    setPending(true);
    setError("");
    try {
      const sourceId = keepId === target.id ? source.id : target.id;
      await api(`/candidates/${sourceId}/merge`, {
        method: "POST",
        body: JSON.stringify({ into_id: keepId }),
      });
      setOpen(false);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["cv-bank"] }),
        client.invalidateQueries({ queryKey: ["bank-suggestions"] }),
        client.invalidateQueries({ queryKey: ["job-ranking"] }),
        client.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      setPending(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!pending) {
          setError("");
          setOpen(value);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline">{t("bank.merge")}</Button>
      </DialogTrigger>
      <DialogContent
        className="max-h-[90vh] max-w-3xl overflow-y-auto"
        closeDisabled={pending}
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          cancel.current?.focus();
        }}
        onEscapeKeyDown={(e) => {
          if (pending) e.preventDefault();
        }}
        onInteractOutside={(e) => {
          if (pending) e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("bank.mergeTitle")}</DialogTitle>
          <DialogDescription>{t("bank.mergeWarning")}</DialogDescription>
        </DialogHeader>
        <fieldset disabled={pending} className="space-y-3">
          <legend className="mb-3 font-medium">{t("bank.keep")}</legend>
          <div className="grid grid-cols-2 gap-4">
            {[source, target].map((candidate) => (
              <BankCandidateCard key={candidate.id} candidate={candidate}>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="merge-target"
                    value={candidate.id}
                    checked={keepId === candidate.id}
                    onChange={() => setKeepId(candidate.id)}
                  />
                  <span>
                    {t("bank.keepThis")}
                    {candidate.full_name}
                  </span>
                </label>
              </BankCandidateCard>
            ))}
          </div>
        </fieldset>
        {error && <p role="alert">{error}</p>}
        <DialogFooter>
          <Button ref={cancel} variant="outline" disabled={pending} onClick={() => setOpen(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="destructive" disabled={pending} onClick={merge}>
            {t(pending ? "common.processing" : "bank.confirmMerge")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
