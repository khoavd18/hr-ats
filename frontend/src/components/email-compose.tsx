"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import type { EmailDraft, EmailMessage } from "@/lib/email-types";
import { t } from "@/i18n/vi";

export function EmailCompose({ draft, onClose }: { draft: EmailDraft; onClose: () => void }) {
  const client = useQueryClient();
  const [to, setTo] = useState(draft.to_email);
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  function refresh() {
    void client.invalidateQueries({ queryKey: ["application-emails", draft.application_id] });
    void client.invalidateQueries({ queryKey: ["application-profile", draft.application_id] });
  }
  async function act(send: boolean) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      let id = saved;
      if (send && !id) {
        const created = await api<EmailMessage>("/email-messages", {
          method: "POST",
          body: JSON.stringify({
            application_id: draft.application_id,
            template_id: draft.template_id,
            to_email: to.trim(),
            subject: subject.trim(),
            body: body.trim(),
          }),
        });
        if (!mounted.current) return;
        id = created.id;
        setSaved(id);
      }
      if (id) {
        await api(`/email-messages/${id}/${send ? "send" : "cancel"}`, { method: "POST" });
        if (!mounted.current) return;
        refresh();
      }
      if (send) toast.success(t("email.queued"));
      onClose();
    } catch (err) {
      if (mounted.current) {
        setError(err instanceof ApiError ? err.message : t("api.unknown"));
        refresh();
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  const frozen = busy || saved !== null;
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !lock.current) void act(false);
      }}
    >
      <DialogContent
        className="max-h-[90vh] overflow-y-auto sm:max-w-2xl"
        closeDisabled={busy}
        onEscapeKeyDown={(event) => {
          if (lock.current) event.preventDefault();
        }}
        onPointerDownOutside={(event) => {
          if (lock.current) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("pipeline.emailPreview")}</DialogTitle>
          <DialogDescription>{t("email.help")}</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void act(true);
          }}
        >
          <label className="block space-y-1">
            <span>{t("email.to")}</span>
            <input
              type="email"
              required
              maxLength={254}
              disabled={frozen}
              value={to}
              onChange={(event) => setTo(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3"
            />
          </label>
          <label className="block space-y-1">
            <span>{t("email.subject")}</span>
            <input
              required
              maxLength={500}
              disabled={frozen}
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3"
            />
          </label>
          <label className="block space-y-1">
            <span>{t("email.body")}</span>
            <textarea
              required
              maxLength={100000}
              disabled={frozen}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              className="min-h-56 w-full rounded-md border bg-background p-3"
            />
          </label>
          {draft.has_calendar && <p className="text-sm">{t("email.calendar")}</p>}
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={busy} onClick={() => void act(false)}>
              {t("email.skip")}
            </Button>
            <Button type="submit" disabled={busy || !to.trim() || !subject.trim() || !body.trim()}>
              {t(busy ? "common.processing" : "email.send")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
