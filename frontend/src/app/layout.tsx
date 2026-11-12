import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

import { Providers } from "@/components/providers";
import { StagingBanner } from "@/components/staging-banner";

// Inter, served by Next.js from our own domain (D-004).
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SchoolFlow Result Portal",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // next-themes sets data-theme before the first paint, so suppressHydrationWarning.
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-bg text-text antialiased">
        {/* APP_ENV is read when the page is built: "staging" on Vercel Preview. */}
        <StagingBanner appEnv={process.env.APP_ENV} />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
