// The strip at the top of every page on staging (D-121), so nobody mistakes
// staging for the real site. Wording approved by Chidimma on 2026-10-12.
// Shown only when APP_ENV is exactly "staging"; production, local and an
// unset value all render nothing.
import { TriangleAlert } from "lucide-react";

type StagingBannerProps = {
  appEnv: string | undefined;
};

export function StagingBanner({ appEnv }: StagingBannerProps) {
  if (appEnv !== "staging") {
    return null;
  }

  return (
    <div
      role="note"
      className="flex items-center justify-center gap-2 bg-(--warning-soft) px-4 py-2 text-sm font-medium text-(--warning-ink)"
    >
      <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
      Staging site: test data only
    </div>
  );
}
