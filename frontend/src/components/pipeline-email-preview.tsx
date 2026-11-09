"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/i18n/vi";
import { EmailCompose } from "@/components/email-compose";
import type { EmailDraft } from "@/lib/email-types";

function isDraft(value: unknown): value is EmailDraft {
  if (!value || typeof value !== "object") return false;
  return ["application_id", "to_email", "subject", "body"].every(
    (field) => field in value && typeof (value as Record<string, unknown>)[field] === "string",
  );
}
export function PipelineEmailPreview({
  draft,
  onClose,
}: {
  draft: unknown | null;
  onClose: () => void;
}) {
  if (isDraft(draft)) return <EmailCompose draft={draft} onClose={onClose} />;
  return (
    <Dialog
      open={draft !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("pipeline.emailPreview")}</DialogTitle>
          <DialogDescription>{t("pipeline.emailPending")}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("common.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
