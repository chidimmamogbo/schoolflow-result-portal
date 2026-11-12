"use client";

// Sessions and terms: add a session, its terms with dates, and choose the active term.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { Card, EmptyState, LoadingState } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { KEYS } from "@/lib/api/school";
import { date } from "@/lib/format";

const TERM = ["", "First Term", "Second Term", "Third Term"];

function NewTerm({ sessionId, taken }: { sessionId: string; taken: number[] }) {
  const free = [1, 2, 3].filter((n) => !taken.includes(n));
  const [v, setV] = useState({
    term_number: String(free[0] ?? ""),
    starts_on: "",
    ends_on: "",
    next_term_begins: "",
  });
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/sessions/{session_id}/terms", {
          params: { path: { session_id: sessionId } },
          body: {
            term_number: Number(v.term_number),
            starts_on: v.starts_on,
            ends_on: v.ends_on,
            next_term_begins: v.next_term_begins || null,
          },
        }),
      ),
    { invalidate: [[...KEYS.sessions]], done: "Term added." },
  );
  if (!free.length) return null;
  return (
    <div className="mt-4 grid gap-3 md:grid-cols-5 md:items-end">
      <Field label="Term">
        {(f) => (
          <Select
            {...f}
            value={v.term_number}
            onChange={(e) => setV({ ...v, term_number: e.target.value })}
          >
            {free.map((n) => (
              <option key={n} value={n}>
                {TERM[n]}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Starts">
        {(f) => (
          <Input
            {...f}
            type="date"
            value={v.starts_on}
            onChange={(e) => setV({ ...v, starts_on: e.target.value })}
          />
        )}
      </Field>
      <Field label="Ends">
        {(f) => (
          <Input
            {...f}
            type="date"
            value={v.ends_on}
            onChange={(e) => setV({ ...v, ends_on: e.target.value })}
          />
        )}
      </Field>
      <Field label="Next term begins">
        {(f) => (
          <Input
            {...f}
            type="date"
            value={v.next_term_begins}
            onChange={(e) => setV({ ...v, next_term_begins: e.target.value })}
          />
        )}
      </Field>
      <Button
        disabled={!v.starts_on || !v.ends_on}
        busy={add.isPending}
        onClick={() => add.mutate(undefined)}
      >
        Add term
      </Button>
    </div>
  );
}

export function SessionsTab() {
  const { data, isPending } = useApi([...KEYS.sessions], () =>
    ok(api.GET("/api/v1/school/sessions")),
  );
  const [v, setV] = useState({ name: "", starts_on: "", ends_on: "" });
  const add = useAction(
    () => ok(api.POST("/api/v1/school/sessions", { body: v })),
    {
      invalidate: [[...KEYS.sessions]],
      done: "Session added.",
      onDone: () => setV({ name: "", starts_on: "", ends_on: "" }),
    },
  );
  const activate = useAction(
    (term: string) =>
      ok(
        api.POST("/api/v1/school/terms/{term_id}/activate", {
          params: { path: { term_id: term } },
        }),
      ),
    {
      invalidate: [[...KEYS.sessions], ["me"]],
      done: "Active term changed.",
    },
  );
  if (isPending) return <LoadingState />;
  return (
    <div className="grid gap-4">
      {data?.length ? null : (
        <EmptyState
          title="No sessions yet."
          body="Add the school year, then its terms."
        />
      )}
      {data?.map((s) => (
        <Card key={s.id}>
          <h3 className="text-lg font-semibold">{s.name}</h3>
          <p className="text-muted">
            {date(s.starts_on)} to {date(s.ends_on)}
          </p>
          <ul className="mt-3 grid gap-2">
            {s.terms.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-3">
                <span className="font-medium">{TERM[t.term_number]}</span>
                <span className="text-muted">
                  {date(t.starts_on)} to {date(t.ends_on)}
                </span>
                {t.is_active ? (
                  <StatusBadge status="active" />
                ) : (
                  <Button size="sm" onClick={() => activate.mutate(t.id)}>
                    Make active
                  </Button>
                )}
              </li>
            ))}
          </ul>
          <NewTerm sessionId={s.id} taken={s.terms.map((t) => t.term_number)} />
        </Card>
      ))}
      <Card className="grid gap-3 md:grid-cols-4 md:items-end">
        <Field label="Session" hint="For example 2026/2027.">
          {(f) => (
            <Input
              {...f}
              value={v.name}
              onChange={(e) => setV({ ...v, name: e.target.value })}
            />
          )}
        </Field>
        <Field label="Starts">
          {(f) => (
            <Input
              {...f}
              type="date"
              value={v.starts_on}
              onChange={(e) => setV({ ...v, starts_on: e.target.value })}
            />
          )}
        </Field>
        <Field label="Ends">
          {(f) => (
            <Input
              {...f}
              type="date"
              value={v.ends_on}
              onChange={(e) => setV({ ...v, ends_on: e.target.value })}
            />
          )}
        </Field>
        <Button
          variant="primary"
          disabled={!v.name || !v.starts_on || !v.ends_on}
          busy={add.isPending}
          onClick={() => add.mutate(undefined)}
        >
          Add session
        </Button>
      </Card>
    </div>
  );
}
