export type RetentionCandidate = {
  id: string;
  full_name: string | null;
  consent_at: string | null;
  retention_until: string;
  expired_at: string | null;
  purge_pending_at: string | null;
  purged_at: string | null;
};

export type DataRequest = {
  id: string;
  candidate_id: string;
  candidate_name: string | null;
  requested_by_note: string | null;
  kind: string;
  status: string;
  handled_at: string | null;
  created_at: string;
};

export type AuditEntry = {
  id: string;
  actor_id: string | null;
  action: string;
  entity: string;
  entity_id: string;
  occurred_at: string;
};

export type PrivacyList<T> = { items: T[]; total: number };

export function privacyTime(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(new Date(value));
}
