import { describe, expect, expectTypeOf, it } from "vitest";
import { t, vi, type TranslationKey } from "@/i18n/vi";

describe("Vietnamese translations", () => {
  it("returns the exact translation for a valid key", () => {
    expect(t("nav.jobs")).toBe("Việc tuyển dụng");
    expect(t("ai.insufficient")).toBe("Chưa đủ thông tin");
  });

  it("keeps all declared translations non-empty", () => {
    for (const key of Object.keys(vi) as TranslationKey[]) {
      expect(t(key).trim()).not.toBe("");
    }
  });

  it("restricts keys and infers the literal return type", () => {
    expectTypeOf<Parameters<typeof t>[0]>().toEqualTypeOf<TranslationKey>();
    expectTypeOf(t("nav.jobs")).toEqualTypeOf<"Việc tuyển dụng">();
    // @ts-expect-error Unknown translation keys must fail the separate typecheck command.
    t("nav.missing");
  });
});
