"use client";

// School setup: one page, a tab per part of the school's set-up.
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { AssessmentTab } from "@/components/setup/assessment";
import { ClassesTab } from "@/components/setup/classes";
import { GradingTab } from "@/components/setup/grading";
import { SessionsTab } from "@/components/setup/sessions";
import { SkillsTab, TraitsTab } from "@/components/setup/skills";
import { DepartmentsTab, SubjectsTab } from "@/components/setup/subjects";
import { PageHeader } from "@/components/ui/layout";
import { Tabs } from "@/components/ui/tabs";

function Setup() {
  const tab = useSearchParams().get("tab") ?? undefined;
  return (
    <>
      <PageHeader title="School setup" />
      <Tabs
        label="School setup"
        value={undefined}
        tabs={[
          { value: "sessions", label: "Sessions", content: <SessionsTab /> },
          { value: "classes", label: "Classes", content: <ClassesTab /> },
          { value: "subjects", label: "Subjects", content: <SubjectsTab /> },
          {
            value: "departments",
            label: "Departments",
            content: <DepartmentsTab />,
          },
          { value: "grading", label: "Grading", content: <GradingTab /> },
          {
            value: "assessment",
            label: "Assessment",
            content: <AssessmentTab />,
          },
          {
            value: "skills",
            label: "Learning areas and skills",
            content: <SkillsTab />,
          },
          { value: "traits", label: "Rating traits", content: <TraitsTab /> },
        ].sort((a, b) => (a.value === tab ? -1 : b.value === tab ? 1 : 0))}
      />
    </>
  );
}

export default function SchoolSetupPage() {
  return (
    <Suspense>
      <Setup />
    </Suspense>
  );
}
