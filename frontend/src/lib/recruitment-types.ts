export type Interview = {
  id: string;
  round: number;
  scheduled_at: string;
  duration_minutes: number;
  location_or_link: string | null;
  interviewers: string[];
  result: "pending" | "pass" | "fail" | "no_show";
  feedback: string | null;
  updated_at: string;
};
export type Offer = {
  id: string;
  salary: number | null;
  start_date: string | null;
  status: "draft" | "sent" | "accepted" | "declined";
  sent_at: string | null;
  notes: string | null;
  updated_at: string;
};
export type Placement = {
  id: string;
  start_date: string;
  fee_amount: number | null;
  guarantee_until: string | null;
  status: "active" | "left_in_guarantee" | "completed";
  updated_at: string;
};
export type RecruitmentRecords = {
  interviews: Interview[];
  offers: Offer[];
  placement: Placement | null;
};
