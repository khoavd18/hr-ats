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

// T23 owns the draft contract, editable preview and confirmed sending action.
// Keep the draft opaque until then; never render arbitrary provider output as HTML.
export function PipelineEmailPreview({
  draft,
  onClose,
}: {
  draft: unknown | null;
  onClose: () => void;
}) {
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
