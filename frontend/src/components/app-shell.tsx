"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BriefcaseBusiness,
  ChartNoAxesCombined,
  CircleUserRound,
  ClipboardList,
  FolderOpen,
  LayoutDashboard,
  Settings,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { t, type TranslationKey } from "@/i18n/vi";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/api";

const navigation = [
  { href: "/", label: "nav.overview", icon: LayoutDashboard },
  { href: "/jobs", label: "nav.jobs", icon: BriefcaseBusiness },
  { href: "/candidates", label: "nav.candidates", icon: FolderOpen },
  { href: "/tasks", label: "nav.tasks", icon: ClipboardList },
  { href: "/reports", label: "nav.reports", icon: ChartNoAxesCombined },
  { href: "/settings", label: "nav.settings", icon: Settings },
] satisfies { href: string; label: TranslationKey; icon: typeof LayoutDashboard }[];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function signOut() {
    setPending(true);
    setError(null);
    try {
      await logout();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="flex min-h-screen">
      <a
        href="#main-content"
        className="sr-only z-50 rounded bg-card p-3 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        {t("shell.skipToContent")}
      </a>
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r bg-card">
        <Link
          href="/"
          className="flex min-h-20 items-center gap-3 border-b px-6 text-sm font-semibold"
        >
          <span className="rounded-lg bg-primary p-2 text-primary-foreground">
            <BriefcaseBusiness aria-hidden="true" className="size-5" />
          </span>
          <span>{t("app.name")}</span>
        </Link>
        <p className="px-6 pb-3 pt-7 text-xs font-medium text-muted-foreground">
          {t("shell.workspace")}
        </p>
        <nav aria-label={t("nav.label")} className="space-y-1 px-3">
          {navigation
            .filter(
              ({ href }) => href !== "/settings" || user?.role === "admin" || user?.role === "lead",
            )
            .map(({ href, label, icon: Icon }) => {
              const active =
                href === "/"
                  ? pathname === "/"
                  : pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition-colors hover:bg-secondary",
                    active ? "bg-accent text-accent-foreground" : "text-muted-foreground",
                  )}
                >
                  <Icon aria-hidden="true" className="size-5" />
                  {t(label)}
                </Link>
              );
            })}
        </nav>
        <div className="mx-4 mb-5 mt-auto rounded-lg bg-secondary p-4">
          <Sparkles aria-hidden="true" className="mb-2 size-4 text-primary" />
          <p className="text-xs leading-5 text-muted-foreground">{t("shell.aiNote")}</p>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <header
          className="flex min-h-20 items-center justify-end gap-4 border-b bg-card px-8"
          aria-label={t("shell.account")}
        >
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <CircleUserRound aria-hidden="true" className="size-5" />
            <span>{user?.full_name}</span>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button variant="outline" size="sm" disabled={pending} onClick={() => void signOut()}>
            {pending ? t("common.processing") : t("shell.logout")}
          </Button>
        </header>
        <main id="main-content" tabIndex={-1} className="mx-auto max-w-7xl p-8 lg:p-10">
          {children}
        </main>
      </div>
    </div>
  );
}
