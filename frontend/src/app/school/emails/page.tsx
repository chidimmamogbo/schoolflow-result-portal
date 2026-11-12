// Emails: the API has no route for a school's outbox status yet (backend gap,
// D-181), so the page says so rather than showing made-up data.
import { EmptyState, PageHeader } from "@/components/ui/layout";

export default function EmailsPage() {
  return (
    <>
      <PageHeader title="Emails" />
      <EmptyState
        title="Email status isn't available yet."
        body="Emails still go out as usual. This page will list each one with its status once it is ready."
      />
    </>
  );
}
