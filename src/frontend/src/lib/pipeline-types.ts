import type { AiLevel } from "@/components/ai-level-badge";
import type { ProcessingStatus, Stage } from "@/lib/ranking-types";
import type { EmailDraft } from "@/lib/email-types";

export type PipelineCard = {
  id: string;
  candidate_id: string;
  candidate_name: string;
  stage: Stage;
  stage_entered_at: string;
  owner_id: string;
  ai_status: ProcessingStatus;
  ai_level: AiLevel | null;
};
export type Pipeline = {
  columns: { stage: Stage; items: PipelineCard[]; total: number }[];
  total: number;
};
// The board consumes only these fields from ApplicationRead, never the CV or contact data.
export type StageUpdate = Pick<PipelineCard, "id" | "stage" | "stage_entered_at">;
export type MoveResult = {
  application: StageUpdate;
  suggested_email: EmailDraft | null;
  email_notice?: string | null;
};

export const rejectionReasons = [
  "skills",
  "experience",
  "salary",
  "noResponse",
  "unitDeclined",
  "other",
] as const;
export type RejectionReason = (typeof rejectionReasons)[number];
