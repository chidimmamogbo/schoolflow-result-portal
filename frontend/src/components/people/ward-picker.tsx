"use client";

// Choose a pupil and the relationship, for linking a parent to a ward.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { fullName, useStudents } from "@/lib/api/school";

export const RELATIONSHIPS = [
  "Mother",
  "Father",
  "Guardian",
  "Grandparent",
  "Aunt",
  "Uncle",
  "Sibling",
];

export function WardPicker({
  label = "Add child",
  busy,
  onAdd,
  exclude = [],
}: {
  label?: string;
  busy?: boolean;
  onAdd: (ward: { student_id: string; relationship: string }) => void;
  exclude?: string[];
}) {
  const { data: pupils } = useStudents();
  const [student, setStudent] = useState("");
  const [relationship, setRelationship] = useState("Mother");
  const [other, setOther] = useState("");
  const options = (pupils ?? [])
    .filter((p) => !exclude.includes(p.id))
    .sort((a, b) => fullName(a).localeCompare(fullName(b)));
  return (
    <div className="grid gap-3 md:grid-cols-[2fr_1fr_auto] md:items-end">
      <Field label="Child">
        {(f) => (
          <Select
            {...f}
            value={student}
            onChange={(e) => setStudent(e.target.value)}
          >
            <option value="">Choose a pupil</option>
            {options.map((p) => (
              <option
                key={p.id}
                value={p.id}
              >{`${fullName(p)} (${p.admission_number})`}</option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Relationship">
        {(f) => (
          <Select
            {...f}
            value={relationship}
            onChange={(e) => setRelationship(e.target.value)}
          >
            {RELATIONSHIPS.map((r) => (
              <option key={r}>{r}</option>
            ))}
            <option value="other">Other</option>
          </Select>
        )}
      </Field>
      <Button
        disabled={!student || (relationship === "other" && !other.trim())}
        busy={busy}
        onClick={() => {
          onAdd({
            student_id: student,
            relationship:
              relationship === "other" ? other.trim() : relationship,
          });
          setStudent("");
        }}
      >
        {label}
      </Button>
      {relationship === "other" ? (
        <Field label="Relationship (other)">
          {(f) => (
            <Input
              {...f}
              value={other}
              onChange={(e) => setOther(e.target.value)}
            />
          )}
        </Field>
      ) : null}
    </div>
  );
}
