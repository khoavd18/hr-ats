import type { AiLevel } from "@/components/ai-level-badge";

export type Candidate = {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  current_title: string | null;
  years_experience: string | null;
  skills: string[];
  consent_at: string | null;
};
export type Feedback = {
  verdict: "agree" | "disagree";
  corrected_level: AiLevel | null;
  comment: string | null;
};
export type ProfileFile = {
  id: string;
  mime_type: string;
  status: "pending" | "running" | "done" | "failed";
  extracted_text: string | null;
};
export type ProfileActivity = {
  id: string;
  type: string;
  actor_name: string | null;
  occurred_at: string;
  payload: Record<string, unknown>;
};
export type ApplicationDetail = {
  candidate: Candidate;
  application: {
    id: string;
    ai_status: "pending" | "running" | "done" | "failed";
    ai_level: AiLevel | null;
    ai_score: number | null;
    ai_reasons: string[];
    ai_flags: string[];
    ai_criteria: {
      criterion: string;
      kind: "must" | "nice";
      result: "met" | "partial" | "not_met" | "unknown";
      evidence: string | null;
    }[];
  };
  cv_files: ProfileFile[];
  feedback: Feedback | null;
  activities: ProfileActivity[];
};
