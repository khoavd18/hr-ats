import type { AiCounts } from "@/lib/ranking-types";

export const jobStatuses = ["draft", "open", "on_hold", "closed"] as const;
export type JobStatus = (typeof jobStatuses)[number];

export type Choice = { id: string; name: string };
export type JobOptions = { hiring_units: Choice[]; users: Choice[] };
export type Job = {
  id: string;
  title: string;
  description: string;
  hiring_unit_id: string;
  hiring_unit_name: string;
  owner_id: string;
  owner_name: string;
  member_ids: string[];
  must_have: string[];
  nice_to_have: string[];
  status: JobStatus;
  location: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  headcount: number;
  deadline: string | null;
  opened_at: string | null;
  closed_at: string | null;
  needs_rescore: boolean;
  ai_counts?: AiCounts;
};

export type HiringUnit = {
  id: string;
  name: string;
  kind: "client" | "department";
  contact_name: string | null;
  contact_email: string | null;
  notes: string | null;
  is_active: boolean;
};
