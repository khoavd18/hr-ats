import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AuthGate } from "@/components/auth-gate";
import { Providers } from "@/components/providers";
import { t } from "@/i18n/vi";
import "./globals.css";

export const metadata: Metadata = { title: t("app.name"), description: t("app.description") };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <Providers>
          <AuthGate>{children}</AuthGate>
        </Providers>
      </body>
    </html>
  );
}
