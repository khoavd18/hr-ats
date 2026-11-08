import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AiLevelBadge, type AiLevel } from "@/components/ai-level-badge";
import { t, type TranslationKey } from "@/i18n/vi";

describe("AiLevelBadge", () => {
  it.each<[AiLevel, TranslationKey, string, string]>([
    ["high", "ai.high", "bg-emerald-50", "text-emerald-800"],
    ["medium", "ai.medium", "bg-yellow-50", "text-yellow-800"],
    ["low", "ai.low", "bg-rose-50", "text-rose-800"],
    ["insufficient", "ai.insufficient", "bg-slate-100", "text-slate-700"],
  ])(
    "renders level %s with its Vietnamese label and specified color",
    (level, key, background, foreground) => {
      render(<AiLevelBadge level={level} />);
      const badge = screen.getByText(t(key));
      expect(badge).toHaveClass(background, foreground);
      expect(badge).not.toHaveTextContent(/\d/);
    },
  );
});
