"use client";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { t } from "@/i18n/vi";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <EmptyState
      title={t("errors.pageTitle")}
      description={t("errors.pageDescription")}
      action={<Button onClick={reset}>{t("common.retry")}</Button>}
    />
  );
}
