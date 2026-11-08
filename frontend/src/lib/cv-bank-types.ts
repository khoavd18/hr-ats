export const candidateSources = ["upload", "email", "form", "import"] as const;
export type CandidateBrief = {
  id: string;
  full_name: string;
  current_title: string | null;
  years_experience: string | null;
  skills: string[];
  location: string | null;
  source: (typeof candidateSources)[number];
  created_at: string;
};
export type BankCandidate = CandidateBrief & { possible_duplicate: CandidateBrief | null };
export type CandidateList = { items: BankCandidate[]; total: number };
