import type { AiLevel } from "@/components/ai-level-badge";

export const aiLevels = ["high", "medium", "low", "insufficient"] as const;
export const stages = [
  "new",
  "screening",
  "submitted",
  "interview",
  "offer",
  "hired",
  "rejected",
  "withdrawn",
] as const;
export type Stage = (typeof stages)[number];
export type ProcessingStatus = "pending" | "running" | "done" | "failed";
export type AiCounts = Record<AiLevel | "pending" | "running" | "failed", number>;
export type RankedApplication = {
  id: string;
  candidate_id: string;
  candidate_name: string;
  skills: string[];
  years_experience: string | null;
  stage: Stage;
  created_at: string;
  ai_status: ProcessingStatus;
  ai_level: AiLevel | null;
};
export type Ranking = { items: RankedApplication[]; total: number; ai_counts: AiCounts };
export type CvFile = {
  id: string;
  candidate_id: string | null;
  job_id: string | null;
  status: ProcessingStatus;
};
export type CvFileStatus = CvFile & {
  processing_error: { code: string } | null;
  application_id: string | null;
  ai_status: ProcessingStatus | null;
};
export type UploadResponse = {
  items: {
    index: number;
    cv_file: CvFile | null;
    duplicate: boolean;
    error: { code: string } | null;
  }[];
};
