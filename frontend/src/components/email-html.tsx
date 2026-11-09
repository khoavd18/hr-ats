import { t } from "@/i18n/vi";

export function EmailHtml({ html }: { html: string }) {
  return (
    <iframe
      title={t("pipeline.emailPreview")}
      sandbox=""
      className="h-48 w-full border bg-white"
      srcDoc={`<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; base-uri 'none'; form-action 'none'"><meta charset="utf-8">${html}`}
    />
  );
}
