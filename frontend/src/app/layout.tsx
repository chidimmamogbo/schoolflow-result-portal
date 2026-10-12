import type { Metadata } from "next";
import "./globals.css";

import { StagingBanner } from "@/components/staging-banner";

export const metadata: Metadata = {
  title: "SchoolFlow Result Portal",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        {/* APP_ENV is read when the page is built: "staging" on Vercel Preview. */}
        <StagingBanner appEnv={process.env.APP_ENV} />
        {children}
      </body>
    </html>
  );
}
