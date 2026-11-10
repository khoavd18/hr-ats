"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/components/auth-provider";
import { ConsentDialog } from "@/components/consent-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PageHeader } from "@/components/page-header";
import { QueryFeedback } from "@/components/query-feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import {
  privacyTime,
  type AuditEntry,
  type DataRequest,
  type PrivacyList,
  type RetentionCandidate,
} from "@/lib/privacy-types";
import { t, type TranslationKey } from "@/i18n/vi";

const actions: Record<string, TranslationKey> = {
  "candidate.purge": "privacy.action.purge",
  "candidate.consent": "privacy.action.consent",
  "candidate.retention_extend": "privacy.action.extend",
  "data_request.create": "privacy.action.request",
  "candidate.export": "privacy.action.export",
  view: "privacy.action.view",
  download: "privacy.action.download",
  "user.role_change": "privacy.action.role",
};

function Pages({
  page,
  total,
  onPage,
}: {
  page: number;
  total: number;
  onPage: (value: number) => void;
}) {
  return (
    <nav className="flex items-center gap-3" aria-label={t("privacy.pagination")}>
      <Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        {t("privacy.previous")}
      </Button>
      <span>
        {t("privacy.page")} {page} {t("privacy.of")} {Math.max(1, Math.ceil(total / 20))}
      </span>
      <Button variant="outline" disabled={page * 20 >= total} onClick={() => onPage(page + 1)}>
        {t("privacy.next")}
      </Button>
    </nav>
  );
}

function RequestDialog({
  candidate,
  onClose,
  onSaved,
}: {
  candidate: RetentionCandidate;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [note, setNote] = useState("");
  const pending = useRef(false);
  const mutation = useMutation({
    mutationFn: () =>
      api("/data-requests", {
        method: "POST",
        body: JSON.stringify({
          candidate_id: candidate.id,
          kind: "delete",
          requested_by_note: note.trim(),
        }),
      }),
    onSuccess: async () => {
      await onSaved();
      onClose();
    },
  });
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending.current) onClose();
      }}
    >
      <DialogContent
        closeDisabled={mutation.isPending}
        onEscapeKeyDown={(event) => {
          if (pending.current) event.preventDefault();
        }}
        onInteractOutside={(event) => {
          if (pending.current) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("privacy.createRequest")}</DialogTitle>
          <DialogDescription>
            {candidate.full_name}
            {t("common.separator")}
            {t("privacy.requestDescription")}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (pending.current || !note.trim()) return;
            pending.current = true;
            try {
              await mutation.mutateAsync();
            } catch {
              /* Keep the form for retry. */
            } finally {
              pending.current = false;
            }
          }}
        >
          <label className="block space-y-2">
            <span>{t("privacy.requestEvidence")}</span>
            <textarea
              className="min-h-24 w-full rounded-md border p-2"
              required
              maxLength={2000}
              value={note}
              disabled={mutation.isPending}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          {mutation.isError && (
            <p role="alert">
              {mutation.error instanceof ApiError ? mutation.error.message : t("api.unknown")}
            </p>
          )}
          <Button type="submit" disabled={mutation.isPending || !note.trim()}>
            {t(mutation.isPending ? "common.processing" : "privacy.createRequest")}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function PrivacySettings() {
  const { user } = useAuth();
  if (user?.role !== "admin") return null;
  return <PrivacyContent key={user.id} />;
}

function PrivacyContent() {
  const cache = useQueryClient();
  const [state, setState] = useState("expiring");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [requestPage, setRequestPage] = useState(1);
  const [auditPage, setAuditPage] = useState(1);
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [tab, setTab] = useState("retention");
  const [selected, setSelected] = useState<RetentionCandidate | null>(null);
  const [executing, setExecuting] = useState<DataRequest | null>(null);
  const retention = useQuery({
    queryKey: ["privacy", "retention", state, q, page],
    queryFn: ({ signal }) =>
      api<PrivacyList<RetentionCandidate>>(
        `/settings/retention?${new URLSearchParams({ state, q, page: String(page) })}`,
        { signal },
      ),
    retry: false,
    gcTime: 0,
  });
  const requests = useQuery({
    queryKey: ["privacy", "requests", requestPage],
    queryFn: ({ signal }) =>
      api<PrivacyList<DataRequest>>(`/data-requests?page=${requestPage}`, { signal }),
    retry: false,
    gcTime: 0,
    enabled: tab === "requests",
  });
  const users = useQuery({
    queryKey: ["privacy", "users"],
    queryFn: async ({ signal }) => {
      const result: { id: string; full_name: string }[] = [];
      for (let page = 1; ; page++) {
        const chunk = await api<PrivacyList<{ id: string; full_name: string }>>(
          `/users?page=${page}&page_size=100`,
          { signal },
        );
        result.push(...chunk.items);
        if (result.length >= chunk.total || !chunk.items.length) return result;
      }
    },
    retry: false,
    gcTime: 0,
    enabled: tab === "audit",
  });
  const audit = useQuery({
    queryKey: ["privacy", "audit", actor, action, auditPage],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ page: String(auditPage), action });
      if (actor === "system") params.set("system", "true");
      else if (actor) params.set("actor_id", actor);
      return api<PrivacyList<AuditEntry>>(`/audit-log?${params}`, { signal });
    },
    retry: false,
    gcTime: 0,
    enabled: tab === "audit",
  });
  async function refresh() {
    await cache.invalidateQueries({ queryKey: ["privacy"] });
  }
  async function execute() {
    if (!executing) return;
    await api(`/data-requests/${executing.id}/execute`, { method: "POST" });
    // Remove cached personal profiles after erasure.
    cache.removeQueries({ queryKey: ["application-profile"] });
    await refresh();
  }
  return (
    <div className="space-y-6">
      <PageHeader title={t("privacy.title")} description={t("privacy.description")} />
      <Tabs value={tab} onValueChange={setTab} className="space-y-4">
        <TabsList aria-label={t("privacy.title")}>
          <TabsTrigger value="retention">{t("privacy.retention")}</TabsTrigger>
          <TabsTrigger value="requests">{t("privacy.requests")}</TabsTrigger>
          <TabsTrigger value="audit">{t("privacy.audit")}</TabsTrigger>
        </TabsList>
        <TabsContent value="retention" className="space-y-4">
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              setQ(search.trim());
              setPage(1);
            }}
          >
            <label className="space-y-1">
              <span className="block">{t("privacy.state")}</span>
              <select
                className="h-10 rounded-md border px-3"
                value={state}
                onChange={(event) => {
                  setState(event.target.value);
                  setPage(1);
                }}
              >
                <option value="expiring">{t("privacy.expiring")}</option>
                <option value="expired">{t("privacy.expired")}</option>
                <option value="all">{t("privacy.all")}</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="block">{t("privacy.search")}</span>
              <Input
                value={search}
                maxLength={200}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <Button type="submit">{t("privacy.searchButton")}</Button>
          </form>
          <QueryFeedback
            pending={retention.isPending}
            error={retention.error}
            retry={() => void retention.refetch()}
          />
          {retention.data && !retention.isError && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="p-3">{t("profile.name")}</th>
                      <th>{t("privacy.until")}</th>
                      <th>{t("privacy.consent")}</th>
                      <th>{t("privacy.actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {retention.data.items.map((row) => (
                      <tr key={row.id} className="border-t">
                        <td className="p-3">
                          {row.full_name ?? t("privacy.anonymous")}
                          {row.purge_pending_at && (
                            <p className="text-amber-800">{t("privacy.frozen")}</p>
                          )}
                        </td>
                        <td>{row.retention_until.split("-").reverse().join("/")}</td>
                        <td>
                          {row.consent_at ? privacyTime(row.consent_at) : t("profile.noConsent")}
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            {!row.purge_pending_at && (
                              <ConsentDialog candidateId={row.id} extend onSaved={refresh} />
                            )}
                            <Button variant="outline" onClick={() => setSelected(row)}>
                              {t("privacy.createRequest")}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!retention.data.items.length && <p>{t("privacy.empty")}</p>}
              <Pages page={page} total={retention.data.total} onPage={setPage} />
            </>
          )}
        </TabsContent>
        <TabsContent value="requests" className="space-y-4">
          <QueryFeedback
            pending={requests.isPending}
            error={requests.error}
            retry={() => void requests.refetch()}
          />
          {requests.data && !requests.isError && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="p-3">{t("profile.name")}</th>
                      <th>{t("privacy.requestEvidence")}</th>
                      <th>{t("privacy.requestedAt")}</th>
                      <th>{t("privacy.state")}</th>
                      <th>{t("privacy.actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.data.items.map((row) => (
                      <tr key={row.id} className="border-t">
                        <td className="p-3">{row.candidate_name ?? t("privacy.anonymous")}</td>
                        <td className="max-w-sm break-words p-3">
                          {row.requested_by_note ?? t("privacy.anonymous")}
                        </td>
                        <td>{privacyTime(row.created_at)}</td>
                        <td>
                          {t(
                            row.status === "done"
                              ? "privacy.done"
                              : row.status === "open"
                                ? "privacy.open"
                                : "privacy.rejected",
                          )}
                        </td>
                        <td>
                          {row.status === "open" && row.kind === "delete" && (
                            <Button variant="destructive" onClick={() => setExecuting(row)}>
                              {t("privacy.execute")}
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!requests.data.items.length && <p>{t("privacy.empty")}</p>}
              <Pages page={requestPage} total={requests.data.total} onPage={setRequestPage} />
            </>
          )}
        </TabsContent>
        <TabsContent value="audit" className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <label className="space-y-1">
              <span className="block">{t("privacy.actor")}</span>
              <select
                className="h-10 rounded-md border px-3"
                value={actor}
                onChange={(event) => {
                  setActor(event.target.value);
                  setAuditPage(1);
                }}
              >
                <option value="">{t("privacy.everyone")}</option>
                <option value="system">{t("profile.system")}</option>
                {users.data?.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.full_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="block">{t("privacy.action")}</span>
              <select
                className="h-10 rounded-md border px-3"
                value={action}
                onChange={(event) => {
                  setAction(event.target.value);
                  setAuditPage(1);
                }}
              >
                <option value="">{t("privacy.allActions")}</option>
                {Object.entries(actions).map(([value, label]) => (
                  <option key={value} value={value}>
                    {t(label)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <QueryFeedback
            pending={users.isPending}
            error={users.error}
            retry={() => void users.refetch()}
          />
          <QueryFeedback
            pending={audit.isPending}
            error={audit.error}
            retry={() => void audit.refetch()}
          />
          {audit.data && !audit.isError && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="p-3">{t("privacy.when")}</th>
                      <th>{t("privacy.actor")}</th>
                      <th>{t("privacy.action")}</th>
                      <th>{t("privacy.reference")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.data.items.map((row) => (
                      <tr key={row.id} className="border-t">
                        <td className="p-3">{privacyTime(row.occurred_at)}</td>
                        <td>
                          {row.actor_id
                            ? (users.data?.find((person) => person.id === row.actor_id)
                                ?.full_name ?? t("privacy.unknownActor"))
                            : t("profile.system")}
                        </td>
                        <td>{t(actions[row.action] ?? "privacy.otherAction")}</td>
                        <td className="max-w-48 break-all">{row.entity_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!audit.data.items.length && <p>{t("privacy.empty")}</p>}
              <Pages page={auditPage} total={audit.data.total} onPage={setAuditPage} />
            </>
          )}
        </TabsContent>
      </Tabs>
      {selected && (
        <RequestDialog
          candidate={selected}
          onClose={() => setSelected(null)}
          onSaved={async () => {
            await refresh();
            setTab("requests");
          }}
        />
      )}
      <ConfirmDialog
        open={!!executing}
        onOpenChange={(open) => {
          if (!open) setExecuting(null);
        }}
        title={t("privacy.executeTitle")}
        description={`${executing?.candidate_name ?? t("privacy.anonymous")}${t("common.separator")}${t("privacy.executeDescription")}`}
        confirmLabel={t("privacy.execute")}
        destructive
        onConfirm={execute}
      />
    </div>
  );
}
