"use client";

import { useDraggable, useDroppable } from "@dnd-kit/core";
import { GripVertical } from "lucide-react";
import { AiLevelBadge } from "@/components/ai-level-badge";
import { Button } from "@/components/ui/button";
import type { Pipeline, PipelineCard } from "@/lib/pipeline-types";
import { cn } from "@/lib/utils";
import { t } from "@/i18n/vi";

function Card({
  card,
  disabled,
  onOpen,
}: {
  card: PipelineCard;
  disabled: boolean;
  onOpen: (card: PipelineCard, trigger: HTMLButtonElement) => void;
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, isDragging } =
    useDraggable({
      id: card.id,
      disabled: disabled || ["hired", "rejected", "withdrawn"].includes(card.stage),
    });
  const days = Math.max(0, Math.floor((Date.now() - Date.parse(card.stage_entered_at)) / 86400000));
  return (
    <li
      ref={setNodeRef}
      className={cn(
        "rounded-lg border bg-card p-3 shadow-sm",
        isDragging && "relative z-10 opacity-70",
      )}
      style={
        transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined
      }
    >
      <div className="flex items-start gap-2">
        <Button
          ref={setActivatorNodeRef}
          variant="ghost"
          size="icon"
          className="size-7 shrink-0 touch-none cursor-grab active:cursor-grabbing"
          {...attributes}
          {...listeners}
          aria-roledescription={t("pipeline.draggable")}
          aria-label={t("pipeline.drag").replace("{name}", card.candidate_name)}
        >
          <GripVertical aria-hidden="true" className="size-4" />
        </Button>
        <button
          className="min-w-0 flex-1 truncate text-left font-medium text-primary underline-offset-4 hover:underline focus-visible:underline"
          title={card.candidate_name}
          onClick={(event) => onOpen(card, event.currentTarget)}
        >
          {card.candidate_name}
        </button>
      </div>
      <div className="mt-3">
        {card.ai_status === "done" && card.ai_level ? (
          <AiLevelBadge level={card.ai_level} />
        ) : (
          <span className="text-sm text-muted-foreground">
            {t(card.ai_status === "failed" ? "ranking.aiFailed" : "upload.scoring")}
          </span>
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        <time
          dateTime={card.stage_entered_at}
          title={new Intl.DateTimeFormat("vi-VN", {
            timeZone: "Asia/Ho_Chi_Minh",
            dateStyle: "short",
            timeStyle: "short",
          }).format(new Date(card.stage_entered_at))}
        >
          {t("pipeline.days").replace("{days}", new Intl.NumberFormat("vi-VN").format(days))}
        </time>
      </p>
    </li>
  );
}

export function PipelineColumn({
  column,
  disabled,
  onOpen,
}: {
  column: Pipeline["columns"][number];
  disabled: boolean;
  onOpen: (card: PipelineCard, trigger: HTMLButtonElement) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.stage, disabled });
  return (
    <section
      ref={setNodeRef}
      aria-label={t(`stage.${column.stage}`)}
      className={cn(
        "min-h-72 w-60 shrink-0 rounded-lg border bg-muted/40 p-3",
        isOver && "border-primary bg-accent",
      )}
    >
      <h3 className="mb-4 flex items-center justify-between gap-2 text-sm font-semibold">
        <span>{t(`stage.${column.stage}`)}</span>
        <span className="rounded-full bg-background px-2 py-1 tabular-nums">{column.total}</span>
      </h3>
      <ul className="space-y-3">
        {column.items.map((card) => (
          <Card key={card.id} card={card} disabled={disabled} onOpen={onOpen} />
        ))}
      </ul>
      {column.total === 0 && (
        <p className="text-sm text-muted-foreground">{t("pipeline.emptyColumn")}</p>
      )}
    </section>
  );
}
