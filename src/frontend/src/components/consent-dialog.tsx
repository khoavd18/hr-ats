"use client";

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { t } from "@/i18n/vi";

export function ConsentDialog({
  candidateId,
  extend = false,
  onSaved,
}: {
  candidateId: string;
  extend?: boolean;
  onSaved: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState("");
  const [note, setNote] = useState("");
  const pending = useRef(false);
  const mutation = useMutation({
    mutationFn: () =>
      api(`/candidates/${candidateId}/consent`, {
        method: "POST",
        body: JSON.stringify({
          consent_at: `${at}:00+07:00`,
          note: note.trim(),
          extend_retention: extend,
        }),
      }),
    onSuccess: async () => {
      setOpen(false);
      setAt("");
      setNote("");
      await onSaved();
    },
  });
  const label = t(extend ? "privacy.extend" : "privacy.recordConsent");
  return (
    <>
      <Button
        variant="outline"
        onClick={() => {
          mutation.reset();
          setOpen(true);
        }}
      >
        {label}
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!pending.current) setOpen(next);
        }}
      >
        <DialogContent
          closeDisabled={mutation.isPending}
          onEscapeKeyDown={(event) => {
            if (pending.current) event.preventDefault();
          }}
          onInteractOutside={(event) => {
            if (pending.current) event.preventDefault();
          }}
        >
          <DialogHeader>
            <DialogTitle>{label}</DialogTitle>
            <DialogDescription>
              {t(extend ? "privacy.extendDescription" : "privacy.consentDescription")}
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              if (pending.current || !at || !note.trim()) return;
              pending.current = true;
              try {
                await mutation.mutateAsync();
              } catch {
                /* Display the safe error below. */
              } finally {
                pending.current = false;
              }
            }}
          >
            <fieldset disabled={mutation.isPending} className="space-y-4">
              <label className="block space-y-2">
                <span>{t("privacy.consentAt")}</span>
                <Input
                  type="datetime-local"
                  required
                  value={at}
                  onChange={(event) => setAt(event.target.value)}
                />
              </label>
              <label className="block space-y-2">
                <span>{t("privacy.evidence")}</span>
                <textarea
                  className="min-h-24 w-full rounded-md border p-2"
                  required
                  maxLength={2000}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
              </label>
              {mutation.isError && (
                <p role="alert">
                  {mutation.error instanceof ApiError ? mutation.error.message : t("api.unknown")}
                </p>
              )}
              <div className="flex gap-2">
                <Button type="submit" disabled={!at || !note.trim()}>
                  {t(mutation.isPending ? "common.processing" : "common.confirm")}
                </Button>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  {t("common.cancel")}
                </Button>
              </div>
            </fieldset>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
