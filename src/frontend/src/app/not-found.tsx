import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { t } from "@/i18n/vi";

export default function NotFound() {
  return (
    <EmptyState
      title={t("errors.notFoundTitle")}
      description={t("errors.notFoundDescription")}
      action={
        <Button asChild>
          <Link href="/">{t("common.backHome")}</Link>
        </Button>
      }
    />
  );
}
