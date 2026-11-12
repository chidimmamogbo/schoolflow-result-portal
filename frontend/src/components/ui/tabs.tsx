"use client";

// Tabs on Radix: arrow keys move between tabs, and each panel is labelled by its tab.
import { Tabs as Radix } from "radix-ui";
import type { ReactNode } from "react";

type Tab = { value: string; label: string; content: ReactNode };

export function Tabs({
  tabs,
  value,
  onValueChange,
  label,
}: {
  tabs: Tab[];
  value?: string;
  onValueChange?: (value: string) => void;
  label: string;
}) {
  return (
    <Radix.Root
      value={value}
      defaultValue={value === undefined ? tabs[0]?.value : undefined}
      onValueChange={onValueChange}
      className="flex flex-col gap-4"
    >
      <Radix.List
        aria-label={label}
        className="flex gap-1 overflow-x-auto border-b border-border"
      >
        {tabs.map((tab) => (
          <Radix.Trigger
            key={tab.value}
            value={tab.value}
            className="min-h-11 border-b-2 border-transparent px-4 text-sm font-semibold whitespace-nowrap text-muted data-[state=active]:border-primary data-[state=active]:text-primary"
          >
            {tab.label}
          </Radix.Trigger>
        ))}
      </Radix.List>
      {tabs.map((tab) => (
        <Radix.Content key={tab.value} value={tab.value}>
          {tab.content}
        </Radix.Content>
      ))}
    </Radix.Root>
  );
}
