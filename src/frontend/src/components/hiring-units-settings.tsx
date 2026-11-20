"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
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
import type { HiringUnit } from "@/lib/job-types";
import { t } from "@/i18n/vi";

export function HiringUnitsSettings() {
  const { user } = useAuth();
  const allowed = user?.role === "admin" || user?.role === "lead";
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<HiringUnit | "new" | null>(null);
  const [change, setChange] = useState<HiringUnit | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const units = useQuery({
    queryKey: ["hiring-units", page],
    queryFn: ({ signal }) =>
      api<{ items: HiringUnit[]; total: number }>(`/hiring-units?page=${page}&page_size=20`, {
        signal,
      }),
    enabled: allowed,
    retry: false,
  });
  const row = editing && editing !== "new" ? editing : null;

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["hiring-units"] });
    await queryClient.invalidateQueries({ queryKey: ["job-options"] });
    await queryClient.invalidateQueries({ queryKey: ["jobs"] });
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const name = String(data.get("name") ?? "").trim();
    const email = String(data.get("contact_email") ?? "").trim();
    const emailInput = form.elements.namedItem("contact_email") as HTMLInputElement;
    if (!name || !emailInput.validity.valid) {
      setError(t("units.required"));
      (name ? emailInput : (form.elements.namedItem("name") as HTMLElement)).focus();
      return;
    }
    setPending(true);
    setError(null);
    try {
      await api(row ? `/hiring-units/${row.id}` : "/hiring-units", {
        method: row ? "PATCH" : "POST",
        body: JSON.stringify({
          name,
          kind: data.get("kind"),
          contact_name: String(data.get("contact_name") ?? "").trim() || null,
          contact_email: email || null,
          notes: String(data.get("notes") ?? "").trim() || null,
        }),
      });
      setEditing(null);
      toast.success(t("units.saved"));
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("api.unknown"));
    } finally {
      setPending(false);
    }
  }
  if (!allowed) return null;
  return (
    <div className="space-y-6">
      <PageHeader
        title={t("units.title")}
        description={t("units.description")}
        action={
          <Button
            onClick={() => {
              setError(null);
              setEditing("new");
            }}
          >
            {t("units.create")}
          </Button>
        }
      />
      <QueryFeedback
        pending={units.isPending}
        error={units.error}
        retry={() => void units.refetch()}
      />
      {units.data && (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("units.name")}</TableHead>
                  <TableHead>{t("units.kind")}</TableHead>
                  <TableHead>{t("units.contact_name")}</TableHead>
                  <TableHead>{t("users.status")}</TableHead>
                  <TableHead>{t("users.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {units.data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-8 text-center">
                      {t("units.empty")}
                    </TableCell>
                  </TableRow>
                )}
                {units.data.items.map((unit) => (
                  <TableRow key={unit.id}>
                    <TableCell className="max-w-56 truncate" title={unit.name}>
                      {unit.name}
                    </TableCell>
                    <TableCell>{t(`units.${unit.kind}`)}</TableCell>
                    <TableCell className="max-w-48 truncate" title={unit.contact_name ?? undefined}>
                      {unit.contact_name}
                    </TableCell>
                    <TableCell>
                      <Badge variant={unit.is_active ? "secondary" : "outline"}>
                        {unit.is_active ? t("units.active") : t("units.inactive")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setError(null);
                            setEditing(unit);
                          }}
                        >
                          {t("jobs.edit")}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setChange(unit)}>
                          {unit.is_active ? t("units.deactivate") : t("units.activate")}
                        </Button>
                      </div>
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
              disabled={page * 20 >= units.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("users.next")}
            </Button>
          </div>
        </>
      )}
      <Dialog
        open={!!editing}
        onOpenChange={(open) => {
          if (!pending && !open) setEditing(null);
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
            <DialogTitle>{row ? t("units.edit") : t("units.create")}</DialogTitle>
            <DialogDescription>{t("units.description")}</DialogDescription>
          </DialogHeader>
          <form key={row?.id ?? "new"} noValidate onSubmit={save} className="space-y-4">
            <fieldset disabled={pending} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="unit-name">{t("units.name")}</label>
                <Input
                  id="unit-name"
                  name="name"
                  maxLength={200}
                  defaultValue={row?.name}
                  aria-required="true"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="unit-kind" className="block">
                  {t("units.kind")}
                </label>
                <select
                  id="unit-kind"
                  name="kind"
                  className="h-10 w-full rounded-md border bg-background px-3"
                  defaultValue={row?.kind ?? "department"}
                >
                  <option value="department">{t("units.department")}</option>
                  <option value="client">{t("units.client")}</option>
                </select>
              </div>
              {(["contact_name", "contact_email"] as const).map((key) => (
                <div key={key} className="space-y-2">
                  <label htmlFor={`unit-${key}`}>{t(`units.${key}`)}</label>
                  <Input
                    id={`unit-${key}`}
                    name={key}
                    type={key === "contact_email" ? "email" : "text"}
                    maxLength={key === "contact_email" ? 254 : 200}
                    defaultValue={row?.[key] ?? ""}
                  />
                </div>
              ))}
              <div className="space-y-2">
                <label htmlFor="unit-notes">{t("units.notes")}</label>
                <textarea
                  id="unit-notes"
                  name="notes"
                  rows={3}
                  maxLength={10000}
                  className="w-full rounded-md border bg-background p-3 text-sm"
                  defaultValue={row?.notes ?? ""}
                />
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
                  onClick={() => setEditing(null)}
                  disabled={pending}
                >
                  {t("common.cancel")}
                </Button>
                <Button type="submit" disabled={pending}>
                  {pending ? t("common.processing") : t("common.save")}
                </Button>
              </DialogFooter>
            </fieldset>
          </form>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={!!change}
        onOpenChange={(open) => {
          if (!open) setChange(null);
        }}
        title={change?.is_active ? t("units.deactivate") : t("units.activate")}
        description={change?.is_active ? t("units.deactivateHint") : t("units.activateHint")}
        destructive={change?.is_active}
        onConfirm={async () => {
          if (!change) return;
          await api(`/hiring-units/${change.id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !change.is_active }),
          });
          await refresh();
          toast.success(t("units.saved"));
        }}
      />
    </div>
  );
}
