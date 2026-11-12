"use client";

// Create school (NAVIGATION "Create school"): school type, features, billing,
// and the principal, who gets an activation email. No public sign-up.
import Link from "next/link";
import { type FormEvent, useState } from "react";

import { FEATURES, type FeatureSet, PKEYS } from "@/components/platform/data";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, FormError, Input, Select } from "@/components/ui/form";
import { Card, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";

const ALL_ON: FeatureSet = {
  results: true,
  report_cards: true,
  parent_portal: true,
  correction_queue: true,
  notice_board: true,
  email_notifications: true,
};

export default function CreateSchoolPage() {
  const [v, setV] = useState({
    name: "",
    code: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    state: "",
    colour: "#1F4FD8",
    school_type: "secondary_only" as
      "secondary_only" | "nursery_primary" | "all_levels",
    billing: "on" as "on" | "free_pilot",
    principal_name: "",
    principal_username: "",
    principal_email: "",
  });
  const [features, setFeatures] = useState<FeatureSet>(ALL_ON);
  const [error, setError] = useState<string | null>(null);
  const [made, setMade] = useState<string | null>(null);
  const create = useAction(
    () =>
      ok(
        api.POST("/api/v1/platform/schools", {
          body: {
            name: v.name.trim(),
            code: v.code.trim().toUpperCase(),
            email: v.email.trim(),
            phone: v.phone.trim(),
            address: v.address.trim(),
            city: v.city.trim(),
            state: v.state.trim(),
            country: "Nigeria",
            colour: v.colour,
            school_type: v.school_type,
            features,
            billing: v.billing,
            principal: {
              full_name: v.principal_name.trim(),
              username: v.principal_username.trim(),
              email: v.principal_email.trim(),
            },
          },
        }),
      ),
    {
      invalidate: [[...PKEYS.schools]],
      done: "School created. The principal's activation email is on its way.",
      onDone: (r) => setMade(r.id),
    },
  );
  const set = (key: keyof typeof v) => (e: { target: { value: string } }) =>
    setV({ ...v, [key]: e.target.value });
  function submit(event: FormEvent) {
    event.preventDefault();
    const missing = (
      [
        "name",
        "code",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "principal_name",
        "principal_username",
        "principal_email",
      ] as const
    ).filter((k) => !v[k].trim());
    if (missing.length) return setError("Fill in every field.");
    setError(null);
    create.mutate(undefined);
  }
  if (made)
    return (
      <>
        <PageHeader title="Create school" />
        <Card className="grid max-w-md gap-3">
          <p role="status">The school is ready.</p>
          <Link
            className={buttonVariants({ variant: "primary" })}
            href={`/platform/schools/${made}`}
          >
            Open school
          </Link>
        </Card>
      </>
    );
  return (
    <>
      <PageHeader title="Create school" />
      <form
        onSubmit={submit}
        className="grid max-w-[var(--form-max)] gap-4"
        noValidate
      >
        <FormError message={error} />
        <Field label="School name">
          {(f) => <Input {...f} value={v.name} onChange={set("name")} />}
        </Field>
        <Field
          label="School code"
          hint="2 to 10 letters or numbers. Students log in with it."
        >
          {(f) => (
            <Input
              {...f}
              autoCapitalize="characters"
              value={v.code}
              onChange={set("code")}
            />
          )}
        </Field>
        <Field label="School type">
          {(f) => (
            <Select {...f} value={v.school_type} onChange={set("school_type")}>
              <option value="nursery_primary">Nursery and Primary</option>
              <option value="secondary_only">Secondary only</option>
              <option value="all_levels">Nursery, Primary and Secondary</option>
            </Select>
          )}
        </Field>
        <Field label="School email">
          {(f) => (
            <Input
              {...f}
              type="email"
              value={v.email}
              onChange={set("email")}
            />
          )}
        </Field>
        <Field label="Phone">
          {(f) => (
            <Input {...f} type="tel" value={v.phone} onChange={set("phone")} />
          )}
        </Field>
        <Field label="Address">
          {(f) => <Input {...f} value={v.address} onChange={set("address")} />}
        </Field>
        <Field label="Town or city">
          {(f) => <Input {...f} value={v.city} onChange={set("city")} />}
        </Field>
        <Field label="State">
          {(f) => <Input {...f} value={v.state} onChange={set("state")} />}
        </Field>
        <Field label="School colour">
          {(f) => (
            <Input
              {...f}
              type="color"
              className="h-11 w-24 p-1"
              value={v.colour}
              onChange={set("colour")}
            />
          )}
        </Field>
        <Card className="grid gap-1">
          <h2 className="font-semibold">Features</h2>
          {FEATURES.map(([key, label]) => (
            <label key={key} className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                className="size-5"
                checked={features[key]}
                onChange={(e) =>
                  setFeatures({ ...features, [key]: e.target.checked })
                }
              />
              {label}
            </label>
          ))}
        </Card>
        <Field label="Billing">
          {(f) => (
            <Select {...f} value={v.billing} onChange={set("billing")}>
              <option value="on">On</option>
              <option value="free_pilot">Off (free pilot)</option>
            </Select>
          )}
        </Field>
        <Card className="grid gap-3">
          <h2 className="font-semibold">Principal</h2>
          <Field label="Full name">
            {(f) => (
              <Input
                {...f}
                value={v.principal_name}
                onChange={set("principal_name")}
              />
            )}
          </Field>
          <Field label="Username">
            {(f) => (
              <Input
                {...f}
                value={v.principal_username}
                onChange={set("principal_username")}
              />
            )}
          </Field>
          <Field label="Email">
            {(f) => (
              <Input
                {...f}
                type="email"
                value={v.principal_email}
                onChange={set("principal_email")}
              />
            )}
          </Field>
        </Card>
        <div>
          <Button type="submit" variant="primary" busy={create.isPending}>
            Create school
          </Button>
        </div>
      </form>
    </>
  );
}
