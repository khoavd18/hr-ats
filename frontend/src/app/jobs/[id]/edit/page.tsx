import { JobEditor } from "@/components/job-form";

export default async function EditJobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobEditor jobId={id} />;
}
