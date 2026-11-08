import { Badge } from "@/components/ui/badge";
import { t, type TranslationKey } from "@/i18n/vi";
import { cn } from "@/lib/utils";

export type AiLevel = "high" | "medium" | "low" | "insufficient";

const levels: Record<AiLevel, { label: TranslationKey; className: string }> = {
  high: { label: "ai.high", className: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  medium: { label: "ai.medium", className: "border-yellow-200 bg-yellow-50 text-yellow-800" },
  low: { label: "ai.low", className: "border-rose-200 bg-rose-50 text-rose-800" },
  insufficient: {
    label: "ai.insufficient",
    className: "border-slate-200 bg-slate-100 text-slate-700",
  },
};

export function AiLevelBadge({ level, className }: { level: AiLevel; className?: string }) {
  const style = levels[level];
  return (
    <Badge variant="outline" className={cn(style.className, className)}>
      {t(style.label)}
    </Badge>
  );
}
