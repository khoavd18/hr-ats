"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n/vi";
import { applicationPath } from "@/lib/application-link";

export function AuthGate({ children }: { children: ReactNode }) {
  const { user, loading, error, reload } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/login";
  const forbidden = pathname.startsWith("/settings") && user?.role === "recruiter";
  useEffect(() => {
    if (loading || error) return;
    if (!user && !isLogin) {
      router.replace(
        applicationPath.test(pathname) ? `/login?next=${encodeURIComponent(pathname)}` : "/login",
      );
    }
    if (user && (isLogin || forbidden)) {
      const next = isLogin ? new URLSearchParams(window.location.search).get("next") : null;
      router.replace(next && applicationPath.test(next) ? next : "/");
    }
  }, [user, loading, error, isLogin, forbidden, router, pathname]);

  if (loading)
    return (
      <p role="status" className="p-10">
        {t("common.loading")}
      </p>
    );
  if (error && !isLogin) {
    return (
      <div className="space-y-4 p-10">
        <p role="alert">{error}</p>
        <Button onClick={() => void reload()}>{t("common.retry")}</Button>
      </div>
    );
  }
  if (isLogin) return user ? null : children;
  if (!user || forbidden) return null;
  return <AppShell>{children}</AppShell>;
}
