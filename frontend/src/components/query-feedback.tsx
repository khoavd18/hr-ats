"use client";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { t } from "@/i18n/vi";

export function QueryFeedback({
  pending,
  error,
  retry,
}: {
  pending: boolean;
  error: Error | null;
  retry: () => void;
}) {
  if (pending) return <p role="status">{t("common.loading")}</p>;
  if (!error) return null;
  return (
    <div className="space-y-3">
      <p role="alert">{error instanceof ApiError ? error.message : t("api.unknown")}</p>
      <Button variant="outline" onClick={retry}>
        {t("common.retry")}
      </Button>
    </div>
  );
}
