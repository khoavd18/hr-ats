"use client";

import { useEffect, useRef, useState } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  pointerWithin,
  useSensor,
  useSensors,
  type DragEndEvent,
  type KeyboardCoordinateGetter,
} from "@dnd-kit/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PipelineColumn } from "@/components/pipeline-column";
import { PipelineEmailPreview } from "@/components/pipeline-email-preview";
import { CandidateProfile } from "@/components/candidate-profile";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { api, ApiError } from "@/lib/api";
import { stages, type Stage } from "@/lib/ranking-types";
import {
  rejectionReasons,
  type MoveResult,
  type Pipeline,
  type PipelineCard,
  type RejectionReason,
  type StageUpdate,
} from "@/lib/pipeline-types";
import { t } from "@/i18n/vi";

// One left/right key moves one column (w-60 + gap-4). The server validates transitions.
const columnCoordinates: KeyboardCoordinateGetter = (event, { currentCoordinates }) => {
  if (event.code === "ArrowRight" || event.code === "ArrowLeft") {
    return {
      ...currentCoordinates,
      x: currentCoordinates.x + (event.code === "ArrowRight" ? 256 : -256),
    };
  }
};

function updateStage(data: Pipeline, update: StageUpdate): Pipeline {
  const card = data.columns.flatMap((column) => column.items).find((item) => item.id === update.id);
  if (!card) return data;
  return {
    ...data,
    columns: data.columns.map((column) => {
      const items = column.items.filter((item) => item.id !== update.id);
      if (column.stage === update.stage) items.push({ ...card, ...update });
      items.sort(
        (a, b) => a.stage_entered_at.localeCompare(b.stage_entered_at) || a.id.localeCompare(b.id),
      );
      return { ...column, items, total: items.length };
    }),
  };
}

export function PipelineBoard({ jobId, active = true }: { jobId: string; active?: boolean }) {
  const client = useQueryClient();
  const key = ["job-pipeline", jobId];
  const lock = useRef(false);
  const mounted = useRef(true);
  const notices = useRef(new Map<string, string | number>());
  useEffect(() => {
    mounted.current = true;
    const visibleNotices = notices.current;
    return () => {
      mounted.current = false;
      for (const id of visibleNotices.values()) toast.dismiss(id);
      visibleNotices.clear();
    };
  }, []);
  const [busy, setBusy] = useState(false);
  const [showWithdrawn, setShowWithdrawn] = useState(false);
  const [rejecting, setRejecting] = useState<PipelineCard | null>(null);
  const [reason, setReason] = useState<RejectionReason | "">("");
  const [error, setError] = useState<string | null>(null);
  const [emailDraft, setEmailDraft] = useState<unknown | null>(null);
  const [selected, setSelected] = useState<PipelineCard | null>(null);
  const profileTrigger = useRef<HTMLButtonElement | null>(null);
  const pipeline = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => api<Pipeline>(`/jobs/${jobId}/pipeline`, { signal }),
    enabled: active && !busy,
    retry: false,
    refetchInterval: (query) => (!active || busy || query.state.error ? false : 3000),
  });
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: columnCoordinates, scrollBehavior: "auto" }),
  );

  function invalidateRelated(id: string) {
    void client.invalidateQueries({ queryKey: ["job-ranking", jobId] });
    void client.invalidateQueries({ queryKey: ["jobs"] });
    void client.invalidateQueries({ queryKey: ["application-profile", id] });
  }

  async function undo(id: string) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      await client.cancelQueries({ queryKey: key });
      const update = await api<StageUpdate>(`/applications/${id}/undo`, { method: "POST" });
      if (!mounted.current) return;
      client.setQueryData<Pipeline>(key, (data) => data && updateStage(data, update));
      const notice = notices.current.get(id);
      if (notice !== undefined) toast.dismiss(notice);
      notices.current.delete(id);
      toast.success(t("pipeline.undone"));
      setEmailDraft(null);
      invalidateRelated(id);
    } catch (err) {
      if (!mounted.current) return;
      setError(err instanceof ApiError ? err.message : t("pipeline.undoError"));
      toast.error(t("pipeline.undoError"));
    } finally {
      lock.current = false;
      setBusy(false);
      void client.invalidateQueries({ queryKey: key });
    }
  }

  async function move(card: PipelineCard, stage: Stage, rejectedReason?: RejectionReason) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    await client.cancelQueries({ queryKey: key });
    const previous = client.getQueryData<Pipeline>(key);
    if (previous)
      client.setQueryData(
        key,
        updateStage(previous, { id: card.id, stage, stage_entered_at: new Date().toISOString() }),
      );
    try {
      const result = await api<MoveResult>(`/applications/${card.id}/move`, {
        method: "POST",
        body: JSON.stringify({
          to_stage: stage,
          ...(rejectedReason ? { rejected_reason: t(`pipeline.reason.${rejectedReason}`) } : {}),
        }),
      });
      // Navigation/logout may clear the cache while the request is in flight.
      // Do not repopulate it or show candidate names after the board unmounts.
      if (!mounted.current) return;
      client.setQueryData<Pipeline>(key, (data) => data && updateStage(data, result.application));
      setRejecting(null);
      setReason("");
      setEmailDraft(result.suggested_email ?? null);
      const previousNotice = notices.current.get(card.id);
      if (previousNotice !== undefined) toast.dismiss(previousNotice);
      const notice = toast.success(
        t("pipeline.moved")
          .replace("{name}", card.candidate_name)
          .replace("{stage}", t(`stage.${result.application.stage}`)),
        {
          duration: 10000,
          action: {
            label: t("pipeline.undo"),
            onClick: (event) => {
              if (lock.current) {
                event.preventDefault();
                return;
              }
              void undo(card.id);
            },
          },
        },
      );
      notices.current.set(card.id, notice);
      invalidateRelated(card.id);
    } catch (err) {
      if (!mounted.current) return;
      if (previous) client.setQueryData(key, previous);
      setError(err instanceof ApiError ? err.message : t("pipeline.moveError"));
      toast.error(t("pipeline.moveError"));
    } finally {
      lock.current = false;
      setBusy(false);
      if (!mounted.current) void client.invalidateQueries({ queryKey: key, refetchType: "none" });
    }
  }

  function drop({ active, over }: DragEndEvent) {
    if (!over || lock.current || rejecting || emailDraft !== null) return;
    const stage = stages.find((value) => value === over.id);
    const card = pipeline.data?.columns
      .flatMap((column) => column.items)
      .find((item) => item.id === active.id);
    if (!card || !stage || card.stage === stage) return;
    if (stage === "rejected") {
      setError(null);
      setReason("");
      setRejecting(card);
    } else void move(card, stage);
  }

  const disabled = busy || !!rejecting || emailDraft !== null;
  const openProfile = (card: PipelineCard, trigger: HTMLButtonElement) => {
    profileTrigger.current = trigger;
    setSelected(card);
  };
  return (
    <div className="min-w-0 space-y-4 pt-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">{t("pipeline.help")}</p>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" disabled={disabled}>
              {t("pipeline.more")}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuCheckboxItem checked={showWithdrawn} onCheckedChange={setShowWithdrawn}>
              {t("stage.withdrawn")}
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <QueryFeedback
        pending={pipeline.isPending}
        error={pipeline.error}
        retry={() => {
          void pipeline.refetch();
        }}
      />
      {error && !rejecting && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {busy && <p role="status">{t("common.processing")}</p>}
      {pipeline.data && !pipeline.isError && (
        <>
          {pipeline.data.total === 0 && <p>{t("pipeline.empty")}</p>}
          <DndContext
            sensors={sensors}
            collisionDetection={(args) =>
              args.pointerCoordinates ? pointerWithin(args) : closestCenter(args)
            }
            onDragEnd={drop}
            accessibility={{
              screenReaderInstructions: { draggable: t("pipeline.keyboard") },
              announcements: {
                onDragStart: () => t("pipeline.dragStarted"),
                onDragOver: ({ over }) =>
                  over && stages.includes(over.id as Stage)
                    ? t("pipeline.over").replace("{stage}", t(`stage.${over.id as Stage}`))
                    : t("pipeline.outside"),
                onDragEnd: () => t("pipeline.dragEnded"),
                onDragCancel: () => t("pipeline.dragCancelled"),
              },
            }}
          >
            <div
              className="flex gap-4 overflow-x-auto pb-4"
              tabIndex={0}
              role="region"
              aria-label={t("pipeline.board")}
              aria-busy={busy}
            >
              {pipeline.data.columns
                .filter((column) => column.stage !== "withdrawn" || showWithdrawn)
                .map((column) => (
                  <PipelineColumn
                    key={column.stage}
                    column={column}
                    disabled={disabled}
                    onOpen={openProfile}
                  />
                ))}
            </div>
          </DndContext>
        </>
      )}
      <Dialog
        open={rejecting !== null}
        onOpenChange={(open) => {
          if (!open && !busy) {
            setRejecting(null);
            setReason("");
            setError(null);
          }
        }}
      >
        <DialogContent
          closeDisabled={busy}
          onEscapeKeyDown={(event) => {
            if (busy) event.preventDefault();
          }}
          onPointerDownOutside={(event) => {
            if (busy) event.preventDefault();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("pipeline.rejectTitle")}</DialogTitle>
            <DialogDescription>
              {t("pipeline.rejectHelp").replace("{name}", rejecting?.candidate_name ?? "")}
            </DialogDescription>
          </DialogHeader>
          <label htmlFor="pipeline-reason">{t("pipeline.reason")}</label>
          <select
            id="pipeline-reason"
            required
            disabled={busy}
            className="h-10 rounded-md border bg-background px-3"
            value={reason}
            onChange={(event) => setReason(event.target.value as RejectionReason | "")}
          >
            <option value="">{t("pipeline.chooseReason")}</option>
            {rejectionReasons.map((value) => (
              <option key={value} value={value}>
                {t(`pipeline.reason.${value}`)}
              </option>
            ))}
          </select>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => {
                setRejecting(null);
                setReason("");
                setError(null);
              }}
            >
              {t("common.cancel")}
            </Button>
            <Button
              disabled={busy || !reason}
              onClick={() => {
                if (rejecting && reason) void move(rejecting, "rejected", reason);
              }}
            >
              {t(busy ? "common.processing" : "common.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <PipelineEmailPreview draft={emailDraft} onClose={() => setEmailDraft(null)} />
      <Sheet
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <SheetContent
          className="w-[94vw] overflow-y-auto sm:max-w-[1200px]"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            profileTrigger.current?.focus();
          }}
        >
          <SheetHeader>
            <SheetTitle>{selected?.candidate_name ?? t("ranking.profile")}</SheetTitle>
            <SheetDescription>{t("profile.aiHint")}</SheetDescription>
          </SheetHeader>
          {selected && <CandidateProfile key={selected.id} applicationId={selected.id} />}
        </SheetContent>
      </Sheet>
    </div>
  );
}
