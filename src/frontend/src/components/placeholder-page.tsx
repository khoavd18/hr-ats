import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { t, type TranslationKey } from "@/i18n/vi";

const pages = {
  overview: {
    title: "nav.overview",
    description: "overview.description",
    emptyTitle: "overview.emptyTitle",
    emptyDescription: "overview.emptyDescription",
    action: "overview.action",
    href: "/jobs",
  },
  jobs: {
    title: "nav.jobs",
    description: "jobs.description",
    emptyTitle: "jobs.emptyTitle",
    emptyDescription: "jobs.emptyDescription",
    action: "jobs.action",
    href: "/candidates",
  },
  candidates: {
    title: "nav.candidates",
    description: "candidates.description",
    emptyTitle: "candidates.emptyTitle",
    emptyDescription: "candidates.emptyDescription",
    action: "candidates.action",
    href: "/jobs",
  },
  tasks: {
    title: "nav.tasks",
    description: "tasks.description",
    emptyTitle: "tasks.emptyTitle",
    emptyDescription: "tasks.emptyDescription",
    action: "tasks.action",
    href: "/",
  },
  reports: {
    title: "nav.reports",
    description: "reports.description",
    emptyTitle: "reports.emptyTitle",
    emptyDescription: "reports.emptyDescription",
    action: "reports.action",
    href: "/jobs",
  },
  settings: {
    title: "nav.settings",
    description: "settings.description",
    emptyTitle: "settings.emptyTitle",
    emptyDescription: "settings.emptyDescription",
    action: "settings.action",
    href: "/",
  },
} satisfies Record<
  string,
  {
    title: TranslationKey;
    description: TranslationKey;
    emptyTitle: TranslationKey;
    emptyDescription: TranslationKey;
    action: TranslationKey;
    href: string;
  }
>;

export function PlaceholderPage({ page }: { page: keyof typeof pages }) {
  const content = pages[page];
  return (
    <>
      <PageHeader title={t(content.title)} description={t(content.description)} />
      <EmptyState
        title={t(content.emptyTitle)}
        description={t(content.emptyDescription)}
        action={
          <Button asChild>
            <Link href={content.href}>
              {t(content.action)}
              <ArrowRight aria-hidden="true" className="ml-2 size-4" />
            </Link>
          </Button>
        }
      />
    </>
  );
}
