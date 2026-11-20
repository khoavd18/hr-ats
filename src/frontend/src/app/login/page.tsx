"use client";

import { useState, type FormEvent } from "react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n/vi";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError(null);
    try {
      await login(String(data.get("email")), String(data.get("password")));
      form.reset();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-secondary p-8">
      <section className="w-full max-w-md space-y-6 rounded-xl border bg-card p-8 shadow-sm">
        <div className="space-y-2">
          <p className="text-sm font-medium text-primary">{t("app.name")}</p>
          <h1 className="text-2xl font-semibold">{t("auth.login")}</h1>
          <p className="text-sm text-muted-foreground">{t("auth.description")}</p>
        </div>
        <form onSubmit={submit} className="space-y-5">
          <div className="space-y-2">
            <label htmlFor="email">{t("auth.email")}</label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              required
              maxLength={254}
              disabled={pending}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="password">{t("auth.password")}</label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              maxLength={128}
              disabled={pending}
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? t("auth.signingIn") : t("auth.login")}
          </Button>
        </form>
      </section>
    </main>
  );
}
