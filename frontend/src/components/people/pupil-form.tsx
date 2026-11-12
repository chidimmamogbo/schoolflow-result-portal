"use client";

// The pupil's details (D-139: Surname, First name, Other names).
import { type FormEvent, useState } from "react";

import { ArmSelect } from "@/components/people/arm-select";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import type { Pupil } from "@/lib/api/school";

export type PupilDetails = {
  surname: string;
  first_name: string;
  other_names: string | null;
  admission_number: string;
  gender: "female" | "male";
  date_of_birth: string | null;
  house: string | null;
  arm_id?: string | null;
};

export function PupilForm({
  pupil,
  withClass,
  busy,
  submitLabel,
  onSubmit,
}: {
  pupil?: Pupil;
  withClass?: boolean;
  busy: boolean;
  submitLabel: string;
  onSubmit: (details: PupilDetails) => void;
}) {
  const [v, setV] = useState({
    surname: pupil?.surname ?? "",
    first_name: pupil?.first_name ?? "",
    other_names: pupil?.other_names ?? "",
    admission_number: pupil?.admission_number ?? "",
    gender: (pupil?.gender as "female" | "male" | undefined) ?? "",
    date_of_birth: pupil?.date_of_birth ?? "",
    house: pupil?.house ?? "",
    arm_id: "",
  });
  const [missing, setMissing] = useState(false);
  const set = (key: keyof typeof v) => (e: { target: { value: string } }) =>
    setV({ ...v, [key]: e.target.value });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (
      !v.surname.trim() ||
      !v.first_name.trim() ||
      !v.admission_number.trim() ||
      !v.gender
    ) {
      setMissing(true);
      return;
    }
    onSubmit({
      surname: v.surname.trim(),
      first_name: v.first_name.trim(),
      other_names: v.other_names.trim() || null,
      admission_number: v.admission_number.trim(),
      gender: v.gender as "female" | "male",
      date_of_birth: v.date_of_birth || null,
      house: v.house.trim() || null,
      ...(withClass ? { arm_id: v.arm_id || null } : {}),
    });
  }
  const need = (value: string) =>
    missing && !value.trim() ? "This is needed." : undefined;
  return (
    <form
      onSubmit={submit}
      className="grid max-w-[var(--form-max)] gap-4"
      noValidate
    >
      <Field label="Surname" error={need(v.surname)}>
        {(f) => <Input {...f} value={v.surname} onChange={set("surname")} />}
      </Field>
      <Field label="First name" error={need(v.first_name)}>
        {(f) => (
          <Input {...f} value={v.first_name} onChange={set("first_name")} />
        )}
      </Field>
      <Field label="Other names">
        {(f) => (
          <Input {...f} value={v.other_names} onChange={set("other_names")} />
        )}
      </Field>
      <Field label="Admission number" error={need(v.admission_number)}>
        {(f) => (
          <Input
            {...f}
            value={v.admission_number}
            onChange={set("admission_number")}
          />
        )}
      </Field>
      <Field label="Gender" error={need(v.gender)}>
        {(f) => (
          <Select {...f} value={v.gender} onChange={set("gender")}>
            <option value="">Choose</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
          </Select>
        )}
      </Field>
      <Field label="Date of birth">
        {(f) => (
          <Input
            {...f}
            type="date"
            value={v.date_of_birth}
            onChange={set("date_of_birth")}
          />
        )}
      </Field>
      <Field label="House">
        {(f) => <Input {...f} value={v.house} onChange={set("house")} />}
      </Field>
      {withClass ? (
        <Field
          label="Class"
          hint="The pupil takes the class's subjects; change them later if needed."
        >
          {(f) => (
            <ArmSelect {...f} value={v.arm_id} onChange={set("arm_id")} />
          )}
        </Field>
      ) : null}
      <div>
        <Button type="submit" variant="primary" busy={busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
