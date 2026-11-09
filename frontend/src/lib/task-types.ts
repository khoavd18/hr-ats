export type Task = {
  id: string;
  title: string;
  description: string | null;
  assignee_id: string;
  created_by: string;
  job_id: string | null;
  application_id: string | null;
  due_at: string | null;
  status: "todo" | "doing" | "done" | "cancelled";
  completed_at: string | null;
};
export type TaskList = { items: Task[]; total: number };
export type OverviewData = {
  today_tasks: TaskList;
  interviews: {
    id: string;
    application_id: string;
    job_id: string;
    candidate_name: string;
    job_title: string;
    scheduled_at: string;
  }[];
  interview_total: number;
  jobs: { id: string; title: string; deadline: string }[];
  job_total: number;
  unseen_cv_count: number;
};

export function vietnamDay(value: string | Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

export function taskGroup(task: Task, now: Date): "overdue" | "today" | "upcoming" {
  if (!task.due_at) return "upcoming";
  const day = vietnamDay(task.due_at);
  const today = vietnamDay(now);
  return day < today ? "overdue" : day === today ? "today" : "upcoming";
}

export function vietnamTime(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}
