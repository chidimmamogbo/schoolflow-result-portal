"use client";

// A class (arm) picker built from the school's classes: "JSS 1A", "Nursery 2".
import type { ComponentProps } from "react";

import { Select } from "@/components/ui/form";
import { armNames, useClasses } from "@/lib/api/school";

export function ArmSelect({
  placeholder = "Choose a class",
  ...props
}: ComponentProps<"select"> & { placeholder?: string }) {
  const { data } = useClasses();
  const names = [...armNames(data).entries()].sort((a, b) =>
    a[1].localeCompare(b[1]),
  );
  return (
    <Select {...props}>
      <option value="">{placeholder}</option>
      {names.map(([id, name]) => (
        <option key={id} value={id}>
          {name}
        </option>
      ))}
    </Select>
  );
}
