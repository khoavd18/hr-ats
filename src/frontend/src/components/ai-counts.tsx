import { AiLevelBadge } from "@/components/ai-level-badge";
import { aiLevels, type AiCounts as Counts } from "@/lib/ranking-types";
import { t } from "@/i18n/vi";

export function AiCounts({ counts }: { counts: Counts }) {
  return (
    <div className="flex flex-wrap gap-2" aria-label={t("ranking.counts")}>
      {aiLevels.map((level) => (
        <span key={level} className="inline-flex items-center gap-1 text-sm">
          <AiLevelBadge level={level} />
          {counts[level]}
        </span>
      ))}
      {counts.pending + counts.running > 0 && (
        <span className="text-sm text-muted-foreground">
          {t("ranking.processing")}
          {counts.pending + counts.running}
        </span>
      )}
      {counts.failed > 0 && (
        <span className="text-sm text-destructive">
          {t("ranking.failedCount")}
          {counts.failed}
        </span>
      )}
    </div>
  );
}
