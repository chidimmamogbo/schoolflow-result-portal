"use client";

// School settings > Login page, and the same choices on the super admin's
// school page (SPEC F02 rules 12 and 14, D-182; labels NAVIGATION v0.5.6).
// Only the school uploads its own photo, after the public warning.
import { type FormEvent, useState } from "react";

import { LoginFrame } from "@/components/auth/login-frame";
import { useSchoolLook } from "@/components/auth/school-brand";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import type { components } from "@/lib/api/schema";

export type LoginPage = components["schemas"]["LoginPage"];
export type LoginPageChange = components["schemas"]["LoginPageChange"];

const LAYOUTS = [
  ["half", "Half and half"],
  ["behind", "Picture behind"],
] as const;

const PICTURES = [
  ["pattern", "Pattern"],
  ["people", "People"],
  ["photo", "Your own photo"],
] as const;

export const PHOTO_WARNING =
  "This picture is public on your login page. Use a picture you have permission to share, such as your school building. Don't use pictures where pupils' faces can be recognised.";

function Choice<T extends string>({
  legend,
  name,
  options,
  value,
  disabled,
  onChange,
}: {
  legend: string;
  name: string;
  options: readonly (readonly [T, string])[];
  value: T;
  disabled?: (option: T) => boolean;
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-semibold">{legend}</legend>
      {options.map(([option, label]) => (
        <label
          key={option}
          className="flex min-h-11 items-center gap-3 text-sm has-[:disabled]:text-muted"
        >
          <input
            type="radio"
            name={name}
            value={option}
            checked={value === option}
            disabled={disabled?.(option)}
            onChange={() => onChange(option)}
            className="size-5 accent-[var(--primary)]"
          />
          {label}
        </label>
      ))}
    </fieldset>
  );
}

export function LoginPageEditor({
  page,
  code,
  busy,
  onSave,
  upload,
}: {
  page: LoginPage;
  code: string;
  busy: boolean;
  onSave: (change: LoginPageChange) => void;
  // The school's own upload; left out on the super admin's page.
  upload?: { busy: boolean; send: (file: File) => void };
}) {
  const [layout, setLayout] = useState(page.layout);
  const [picture, setPicture] = useState(page.picture);
  const [message, setMessage] = useState(page.message ?? "");
  const [file, setFile] = useState<File | null>(null);
  const look = useSchoolLook(code);
  const changed =
    layout !== page.layout ||
    picture !== page.picture ||
    message.trim() !== (page.message ?? "");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSave({ layout, picture, message: message.trim() || null });
  };
  const fullLink =
    typeof window === "undefined"
      ? page.link
      : `${window.location.origin}${page.link}`;

  return (
    <div className="grid gap-6">
      <form onSubmit={submit} className="grid gap-5">
        <Choice
          legend="Layout"
          name="login-layout"
          options={LAYOUTS}
          value={layout}
          onChange={setLayout}
        />
        <Choice
          legend="Picture"
          name="login-picture"
          options={PICTURES}
          value={picture}
          disabled={(option) => option === "photo" && !page.photo_url}
          onChange={setPicture}
        />
        <Field
          label="Login page message"
          hint={`Up to 80 characters. Leave it empty to show "Welcome to {School name}".`}
        >
          {(f) => (
            <Input
              {...f}
              maxLength={80}
              value={message}
              onChange={(e) =>
                setMessage(e.target.value.replace(/[\r\n]/g, ""))
              }
            />
          )}
        </Field>
        <div>
          <Button
            type="submit"
            variant="primary"
            disabled={!changed}
            busy={busy}
          >
            Save changes
          </Button>
        </div>
      </form>

      {upload ? (
        <div className="grid gap-2">
          <p className="rounded-md border border-warning bg-warning-soft p-3 text-sm text-warning-ink">
            {PHOTO_WARNING}
          </p>
          <div className="grid gap-2 md:grid-cols-[1fr_auto] md:items-end">
            <Field label="Your own photo" hint="PNG, JPEG or WebP, up to 4 MB.">
              {(f) => (
                <Input
                  {...f}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              )}
            </Field>
            <Button
              disabled={!file}
              busy={upload.busy}
              onClick={() => file && upload.send(file)}
            >
              Upload a photo
            </Button>
          </div>
        </div>
      ) : null}

      <div className="grid gap-2">
        <h3 className="text-sm font-semibold">Preview</h3>
        {look.state === "found" ? (
          <div
            className="pointer-events-none relative h-80 overflow-hidden rounded-md border border-border"
            aria-hidden="true"
            inert
          >
            <div className="w-[250%] origin-top-left scale-[0.4]">
              <LoginFrame
                brand={{
                  ...look.brand,
                  layout,
                  picture,
                  message: message.trim() || null,
                  photoUrl: page.photo_url,
                }}
                title="Welcome back"
              >
                <div className="h-40 rounded-md bg-surface-2" />
              </LoginFrame>
            </div>
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={page.link}
            target="_blank"
            rel="noreferrer"
            className={buttonVariants({ variant: "secondary" })}
          >
            Open login page
          </a>
          <Button
            variant="ghost"
            onClick={() => {
              void navigator.clipboard
                ?.writeText(fullLink)
                .catch(() => undefined);
            }}
          >
            Copy link
          </Button>
          <code className="text-sm text-muted">{fullLink}</code>
        </div>
      </div>
    </div>
  );
}
