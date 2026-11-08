"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { t } from "@/i18n/vi";
import type { User, UserRole } from "@/lib/auth-types";

const roles = ["admin", "lead", "recruiter"] as const;
const selectClass = "h-10 rounded-md border border-input bg-background px-3 text-sm";

export function UsersSettings() {
  const { user: actor } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [change, setChange] = useState<{ user: User; role?: UserRole; is_active?: boolean } | null>(
    null,
  );
  const users = useQuery({
    queryKey: ["users", page],
    queryFn: ({ signal }) =>
      api<{ items: User[]; total: number }>(`/users?page=${page}&page_size=20`, { signal }),
    enabled: actor?.role === "admin",
    retry: false,
  });

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError(null);
    try {
      await api("/users", { method: "POST", body: JSON.stringify(Object.fromEntries(data)) });
      form.reset();
      setCreateOpen(false);
      toast.success(t("users.created"));
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      setPending(false);
    }
  }

  async function confirmChange() {
    if (!change) return;
    const { user, ...patch } = change;
    await api(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify(patch) });
    toast.success(t("users.saved"));
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  if (actor?.role !== "admin") return null;
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("users.title")}
        description={t("users.description")}
        action={
          <Button
            onClick={() => {
              setError(null);
              setCreateOpen(true);
            }}
          >
            {t("users.create")}
          </Button>
        }
      />
      {users.isPending && <p role="status">{t("common.loading")}</p>}
      {users.isError && (
        <div className="space-y-3">
          <p role="alert">
            {users.error instanceof ApiError ? users.error.message : t("api.unknown")}
          </p>
          <Button variant="outline" onClick={() => void users.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {users.data && (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("users.fullName")}</TableHead>
                  <TableHead>{t("auth.email")}</TableHead>
                  <TableHead>{t("users.role")}</TableHead>
                  <TableHead>{t("users.status")}</TableHead>
                  <TableHead>{t("users.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>{t("users.empty")}</TableCell>
                  </TableRow>
                )}
                {users.data.items.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="max-w-48 truncate" title={user.full_name}>
                      {user.full_name}
                    </TableCell>
                    <TableCell className="max-w-60 truncate" title={user.email}>
                      {user.email}
                    </TableCell>
                    <TableCell>
                      <select
                        className={selectClass}
                        value={user.role}
                        disabled={user.id === actor.id}
                        aria-label={`${t("users.edit")}: ${user.full_name}`}
                        onChange={(event) =>
                          setChange({ user, role: event.target.value as UserRole })
                        }
                      >
                        {roles.map((role) => (
                          <option value={role} key={role}>
                            {t(`users.${role}`)}
                          </option>
                        ))}
                      </select>
                    </TableCell>
                    <TableCell>
                      <Badge variant={user.is_active ? "secondary" : "outline"}>
                        {user.is_active ? t("users.active") : t("users.inactive")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={user.id === actor.id}
                        onClick={() => setChange({ user, is_active: !user.is_active })}
                      >
                        {user.is_active ? t("users.lock") : t("users.unlock")}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>
              {t("users.previous")}
            </Button>
            <Button
              variant="outline"
              disabled={page * 20 >= users.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("users.next")}
            </Button>
          </div>
        </>
      )}
      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          if (!pending) setCreateOpen(open);
        }}
      >
        <DialogContent
          closeDisabled={pending}
          onEscapeKeyDown={(event) => {
            if (pending) event.preventDefault();
          }}
          onInteractOutside={(event) => {
            if (pending) event.preventDefault();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("users.create")}</DialogTitle>
            <DialogDescription>{t("users.description")}</DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={create}>
            <div className="space-y-2">
              <label htmlFor="full_name">{t("users.fullName")}</label>
              <Input
                id="full_name"
                name="full_name"
                required
                maxLength={200}
                disabled={pending}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="new_email">{t("auth.email")}</label>
              <Input
                id="new_email"
                name="email"
                type="email"
                required
                maxLength={254}
                disabled={pending}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="new_password">{t("auth.password")}</label>
              <Input
                id="new_password"
                name="password"
                type="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                disabled={pending}
                aria-describedby="password-hint"
              />
              <p id="password-hint" className="text-sm text-muted-foreground">
                {t("users.passwordHint")}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <label htmlFor="new_role">{t("users.role")}</label>
              <select
                id="new_role"
                name="role"
                defaultValue="recruiter"
                className={selectClass}
                disabled={pending}
              >
                {roles.map((role) => (
                  <option value={role} key={role}>
                    {t(`users.${role}`)}
                  </option>
                ))}
              </select>
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() => setCreateOpen(false)}
              >
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={pending}>
                {pending ? t("common.processing") : t("users.create")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={change !== null}
        onOpenChange={(open) => {
          if (!open) setChange(null);
        }}
        title={
          change?.role ? t("users.edit") : change?.is_active ? t("users.unlock") : t("users.lock")
        }
        description={`${change?.user.full_name ?? ""}. ${change?.role ? `${t(`users.${change.role}`)}. ${t("users.roleDescription")}` : change?.is_active ? t("users.unlockDescription") : t("users.lockDescription")}`}
        destructive={change?.is_active === false}
        onConfirm={confirmChange}
      />
    </div>
  );
}
