import type { ReactNode } from "react";
import type { CandidateBrief } from "@/lib/cv-bank-types";
import { t } from "@/i18n/vi";

export function BankCandidateCard({
  candidate,
  children,
}: {
  candidate: CandidateBrief;
  children?: ReactNode;
}) {
  return (
    <article
      className="min-w-0 space-y-3 rounded-lg border bg-card p-4"
      aria-label={candidate.full_name}
    >
      <h3 className="break-words font-semibold">{candidate.full_name}</h3>
      <dl className="space-y-2 text-sm">
        <div>
          <dt className="text-muted-foreground">{t("bank.title")}</dt>
          <dd>{candidate.current_title || t("ranking.unknown")}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("bank.years")}</dt>
          <dd>
            {candidate.years_experience === null
              ? t("ranking.unknown")
              : new Intl.NumberFormat("vi-VN").format(Number(candidate.years_experience))}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("bank.skills")}</dt>
          <dd className="truncate" title={candidate.skills.join(", ")}>
            {candidate.skills.slice(0, 5).join(", ") || t("ranking.unknown")}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("bank.location")}</dt>
          <dd>{candidate.location || t("ranking.unknown")}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("bank.source")}</dt>
          <dd>{t(`bank.source.${candidate.source}`)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("bank.received")}</dt>
          <dd>
            {new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }).format(
              new Date(candidate.created_at),
            )}
          </dd>
        </div>
      </dl>
      {children}
    </article>
  );
}
