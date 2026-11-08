import { t } from "@/i18n/vi";

export default function Loading() {
  return (
    <p role="status" className="text-sm text-muted-foreground">
      {t("common.loading")}
    </p>
  );
}
