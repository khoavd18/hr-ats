import { t } from "@/i18n/vi";
import { emailVariables } from "@/lib/email-types";

export function emailNotice(code: string): string {
  if (code === "EMAIL_NO_ADDRESS") return t("email.noAddress");
  if (code === "EMAIL_UNIT_NO_ADDRESS") return t("email.unitNoAddress");
  const variable = emailVariables.find((name) => code === `EMAIL_MISSING_${name.toUpperCase()}`);
  return variable ? t(`emailTemplates.missing.${variable}`) : t("email.invalidDraft");
}
