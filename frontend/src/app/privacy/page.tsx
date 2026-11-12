// Plain-language privacy notice (F24).
import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-4 px-4 py-12">
      <h1 className="text-3xl font-bold">Privacy</h1>
      <p>
        SchoolFlow Result Portal keeps school results for the schools that use
        it. Each school decides who has an account, and every account belongs to
        one school, except a parent with children in more than one school.
      </p>
      <h2 className="text-xl font-semibold">What we keep</h2>
      <p>
        Names, admission numbers, classes, subjects, scores, ratings, comments
        and attendance that the school enters; parents&apos; and staff names and
        contact details; and a record of who changed what, so results can be
        trusted.
      </p>
      <h2 className="text-xl font-semibold">Who can see it</h2>
      <p>
        Teachers see only the classes and subjects they teach, reviewers only
        their scope, parents only their own children, and students only
        themselves. Results are seen only after the school publishes them.
        Emails never contain scores, and a report card&apos;s QR code holds no
        personal details.
      </p>
      <h2 className="text-xl font-semibold">Your choices</h2>
      <p>
        To see, correct or remove information about you or your child, contact
        your school. The school can export or delete records on your behalf.
      </p>
      <Link href="/" className="font-medium text-primary hover:underline">
        Back to home
      </Link>
    </main>
  );
}
