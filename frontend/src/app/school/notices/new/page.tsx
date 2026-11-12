"use client";

// Post a notice to everyone, or chosen roles, optionally in chosen classes (F17).
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input, Textarea } from "@/components/ui/form";
import { Card, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { useClasses } from "@/lib/api/school";

const ROLES = [
  ["school_admin", "School admins"],
  ["teacher", "Teachers"],
  ["reviewer", "Reviewers"],
  ["parent", "Parents"],
  ["student", "Students"],
] as const;
type Role = (typeof ROLES)[number][0];

export default function NewNoticePage() {
  const router = useRouter();
  const { data: classes } = useClasses();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [pinned, setPinned] = useState(false);
  const [everyone, setEveryone] = useState(true);
  const [roles, setRoles] = useState<Role[]>([]);
  const [classIds, setClassIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const post = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/notices", {
          body: {
            title: title.trim(),
            body: body.trim(),
            pinned,
            audience: everyone
              ? { everyone: true, roles: [], class_ids: [] }
              : { everyone: false, roles, class_ids: classIds },
          },
        }),
      ),
    {
      invalidate: [["school", "notices"]],
      done: "Notice posted.",
      onDone: () => router.push("/school/notices"),
    },
  );
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !body.trim())
      return setError("A title and a message are needed.");
    if (!everyone && !roles.length && !classIds.length)
      return setError("Choose everyone, or roles and classes.");
    setError(null);
    post.mutate(undefined);
  }
  const toggle = <T,>(list: T[], value: T) =>
    list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
  return (
    <>
      <PageHeader title="Post notice" />
      <form
        onSubmit={submit}
        className="grid max-w-[var(--form-max)] gap-4"
        noValidate
      >
        <FormError message={error} />
        <Field label="Title">
          {(f) => (
            <Input
              {...f}
              maxLength={120}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          )}
        </Field>
        <Field label="Message">
          {(f) => (
            <Textarea
              {...f}
              rows={6}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          )}
        </Field>
        <label className="flex min-h-11 items-center gap-2">
          <input
            type="checkbox"
            className="size-5"
            checked={pinned}
            onChange={(e) => setPinned(e.target.checked)}
          />
          Pin to the top
        </label>
        <Card className="grid gap-2">
          <h2 className="font-semibold">Audience</h2>
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              className="size-5"
              checked={everyone}
              onChange={(e) => setEveryone(e.target.checked)}
            />
            Everyone
          </label>
          {everyone ? null : (
            <>
              <div className="flex flex-wrap gap-3">
                {ROLES.map(([value, label]) => (
                  <label
                    key={value}
                    className="flex min-h-11 items-center gap-2"
                  >
                    <input
                      type="checkbox"
                      className="size-5"
                      checked={roles.includes(value)}
                      onChange={() => setRoles(toggle(roles, value))}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <div className="flex flex-wrap gap-3">
                {(classes ?? []).map((c) => (
                  <label
                    key={c.id}
                    className="flex min-h-11 items-center gap-2"
                  >
                    <input
                      type="checkbox"
                      className="size-5"
                      checked={classIds.includes(c.id)}
                      onChange={() => setClassIds(toggle(classIds, c.id))}
                    />
                    {c.name}
                  </label>
                ))}
              </div>
            </>
          )}
        </Card>
        <div>
          <Button type="submit" variant="primary" busy={post.isPending}>
            Post notice
          </Button>
        </div>
      </form>
    </>
  );
}
