import type { Stage } from "@/lib/ranking-types";

export type EmailTemplate = {
  id: string;
  key: string;
  name: string;
  stage: Stage | null;
  subject: string;
  body: string;
  is_active: boolean;
  requires_confirmation: boolean;
};

export type EmailPreview = { subject: string; body: string; body_html: string };
export type EmailDraft = EmailPreview & {
  application_id: string;
  template_id: string | null;
  to_email: string;
  has_calendar: boolean;
};
export type EmailMessage = {
  id: string;
  application_id: string;
  template_id: string | null;
  to_email: string;
  subject: string;
  body_html: string;
  status: "draft" | "queued" | "sent" | "failed" | "cancelled";
  sent_at: string | null;
  scheduled_for: string | null;
  created_at: string;
};
export type PreviewOption = { id: string; candidate_name: string; job_title: string };

export const emailVariables = [
  "candidate_name",
  "job_title",
  "hiring_unit_name",
  "interview_time",
  "interview_location",
  "offer_salary",
  "offer_start_date",
  "recruiter_name",
  "recruiter_email",
  "company_name",
] as const;
