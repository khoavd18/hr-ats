import { notFound } from "next/navigation";
import { CandidateProfile } from "@/components/candidate-profile";
import { applicationPath } from "@/lib/application-link";

export default async function ApplicationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!applicationPath.test(`/applications/${id}`)) notFound();
  return <CandidateProfile applicationId={id} />;
}
