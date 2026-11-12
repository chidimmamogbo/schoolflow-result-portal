"use client";

// School detail (NAVIGATION "School detail tabs"): Overview, Features (with
// Report cards by level), School admins, Subscription, Invoices, Activity.
import { useParams } from "next/navigation";
import { useState } from "react";

import { CredentialSlip } from "@/components/people/login-support";
import { FEATURES, type FeatureSet, PKEYS } from "@/components/platform/data";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, ReasonDialog } from "@/components/ui/dialog";
import { DataTable } from "@/components/ui/data-table";
import { Field, Input } from "@/components/ui/form";
import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date, dateTime, money } from "@/lib/format";

function Admins({ schoolId }: { schoolId: string }) {
  const key = ["platform", "admins", schoolId];
  const { data } = useApi(key, () =>
    ok(
      api.GET("/api/v1/platform/schools/{school_id}/admins", {
        params: { path: { school_id: schoolId } },
      }),
    ),
  );
  const [slip, setSlip] = useState<{
    name: string;
    username: string;
    password: string;
  } | null>(null);
  const p = (user: string) => ({
    params: { path: { school_id: schoolId, user_id: user } },
  });
  const resend = useAction(
    (u: string) =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/admins/{user_id}/resend-activation",
          p(u),
        ),
      ),
    { done: "Activation email sent." },
  );
  const reset = useAction(
    (u: string) =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/admins/{user_id}/send-reset-link",
          { ...p(u), body: { sign_out_all: false } },
        ),
      ),
    { done: "Reset link sent." },
  );
  const temp = useAction(
    (u: { id: string; name: string; username: string }) =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/admins/{user_id}/temporary-password",
          p(u.id),
        ),
      ).then((r) => ({ ...u, password: r.temporary_password })),
    {
      onDone: (r) =>
        setSlip({ name: r.name, username: r.username, password: r.password }),
    },
  );
  const signOut = useAction(
    (u: string) =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/admins/{user_id}/sign-out-all",
          p(u),
        ),
      ),
    { done: "Signed out of all devices." },
  );
  const primary = useAction(
    (u: string) =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/admins/{user_id}/make-primary",
          p(u),
        ),
      ),
    { invalidate: [key], done: "Principal changed." },
  );
  const deactivate = useAction(
    (u: string) =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/admins/{user_id}/deactivate",
          p(u),
        ),
      ),
    { invalidate: [key], done: "Account deactivated." },
  );
  const reactivate = useAction(
    (u: string) =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/admins/{user_id}/reactivate",
          p(u),
        ),
      ),
    { invalidate: [key], done: "Account reactivated." },
  );
  return (
    <div className="grid gap-3">
      {(data ?? []).map((a) => (
        <Card key={a.id} className="grid gap-2">
          <p className="font-semibold">
            {a.full_name}{" "}
            <span className="font-normal text-muted">{`${a.username} · ${a.is_primary ? "Principal" : "School admin"} · ${a.is_active ? (a.activated ? "Active" : "Invited") : "Deactivated"}`}</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {a.email && !a.activated ? (
              <Button size="sm" onClick={() => resend.mutate(a.id)}>
                Resend activation
              </Button>
            ) : null}
            {a.email ? (
              <Button size="sm" onClick={() => reset.mutate(a.id)}>
                Send reset link
              </Button>
            ) : null}
            <Button
              size="sm"
              onClick={() =>
                temp.mutate({
                  id: a.id,
                  name: a.full_name,
                  username: a.username,
                })
              }
            >
              Issue temporary password
            </Button>
            <Button size="sm" onClick={() => signOut.mutate(a.id)}>
              Sign out of all devices
            </Button>
            {a.is_primary ? null : (
              <Button size="sm" onClick={() => primary.mutate(a.id)}>
                Make principal
              </Button>
            )}
            {a.is_active ? (
              <Button
                size="sm"
                variant="danger"
                onClick={() => deactivate.mutate(a.id)}
              >
                Deactivate account
              </Button>
            ) : (
              <Button size="sm" onClick={() => reactivate.mutate(a.id)}>
                Reactivate account
              </Button>
            )}
          </div>
        </Card>
      ))}
      <CredentialSlip
        password={slip?.password ?? null}
        name={slip?.name ?? ""}
        username={slip?.username ?? ""}
        onClose={() => setSlip(null)}
      />
    </div>
  );
}

export default function SchoolDetailPage() {
  const { id } = useParams<{ id: string }>();
  const key = ["platform", "school", id];
  const path = { params: { path: { school_id: id } } };
  const { data, isPending, isError, refetch } = useApi(key, () =>
    ok(api.GET("/api/v1/platform/schools/{school_id}", path)),
  );
  const usage = useApi(["platform", "usage", id], () =>
    ok(api.GET("/api/v1/platform/schools/{school_id}/usage", path)),
  );
  const invoices = useApi(["platform", "invoices", id], () =>
    ok(
      api.GET("/api/v1/platform/invoices", {
        params: { query: { school_id: id } },
      }),
    ),
  );
  const activity = useApi(["platform", "activity", id], () =>
    ok(
      api.GET("/api/v1/platform/schools/{school_id}/activity", {
        params: { path: { school_id: id }, query: { limit: 50 } },
      }),
    ),
  );
  const [ask, setAsk] = useState<"suspend" | "level" | null>(null);
  const [levelChange, setLevelChange] = useState<{
    nursery: boolean;
    primary: boolean;
    secondary: boolean;
  } | null>(null);
  const [grace, setGrace] = useState<string | null>(null);
  const suspend = useAction(
    (reason: string) =>
      ok(
        api.POST("/api/v1/platform/schools/{school_id}/suspend", {
          ...path,
          body: { reason },
        }),
      ),
    {
      invalidate: [key, [...PKEYS.schools]],
      done: "School suspended. No data is deleted.",
      onDone: () => setAsk(null),
    },
  );
  const reactivate = useAction(
    () => ok(api.POST("/api/v1/platform/schools/{school_id}/reactivate", path)),
    { invalidate: [key, [...PKEYS.schools]], done: "School reactivated." },
  );
  const resendSetup = useAction(
    () =>
      ok(
        api.POST(
          "/api/v1/platform/schools/{school_id}/resend-setup-email",
          path,
        ),
      ),
    { done: "Set-up email sent." },
  );
  const features = useAction(
    (f: FeatureSet) =>
      ok(
        api.PUT("/api/v1/platform/schools/{school_id}/features", {
          ...path,
          body: f,
        }),
      ),
    { invalidate: [key], done: "Features saved." },
  );
  const levels = useAction(
    (l: { nursery: boolean; primary: boolean; secondary: boolean }) =>
      ok(
        api.PUT("/api/v1/platform/schools/{school_id}/levels", {
          ...path,
          body: { ...l, confirm: true },
        }),
      ),
    {
      invalidate: [key],
      done: "Report cards by level saved.",
      onDone: () => setAsk(null),
    },
  );
  const subscription = useAction(
    (body: {
      billing_enabled?: boolean | null;
      grace_period_days?: number | null;
      use_platform_grace?: boolean;
      suspended?: boolean | null;
      reason?: string | null;
    }) =>
      ok(
        api.PATCH("/api/v1/platform/schools/{school_id}/subscription", {
          ...path,
          body: { use_platform_grace: false, ...body },
        }),
      ),
    { invalidate: [key], done: "Subscription saved." },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the school" onRetry={() => void refetch()} />;
  const s = data;
  return (
    <>
      <PageHeader
        title={s.name}
        caption={`${s.code} · ${s.city}, ${s.state}`}
        actions={<StatusBadge status={s.status} />}
      />
      <Tabs
        label="School detail"
        tabs={[
          {
            value: "overview",
            label: "Overview",
            content: (
              <div className="grid gap-4">
                <Card className="grid gap-2">
                  <p>{`${s.email} · ${s.phone} · ${s.address}`}</p>
                  {usage.data ? (
                    <p className="text-muted">{`Students ${usage.data.students} · Staff ${usage.data.staff} · Parents ${usage.data.parents} · Results published ${usage.data.results_published}${usage.data.last_activity ? ` · Last activity ${date(usage.data.last_activity)}` : ""}`}</p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => resendSetup.mutate(undefined)}>
                      Resend set-up email
                    </Button>
                    {s.status === "suspended" ? (
                      <Button onClick={() => reactivate.mutate(undefined)}>
                        Reactivate school
                      </Button>
                    ) : (
                      <Button
                        variant="danger"
                        onClick={() => setAsk("suspend")}
                      >
                        Suspend school
                      </Button>
                    )}
                  </div>
                </Card>
              </div>
            ),
          },
          {
            value: "features",
            label: "Features",
            content: (
              <div className="grid gap-4 md:grid-cols-2">
                <Card className="grid gap-1">
                  <h2 className="font-semibold">Features</h2>
                  {FEATURES.map(([k, label]) => (
                    <label key={k} className="flex min-h-11 items-center gap-2">
                      <input
                        type="checkbox"
                        className="size-5"
                        checked={s.features[k]}
                        onChange={(e) =>
                          features.mutate({
                            ...s.features,
                            [k]: e.target.checked,
                          })
                        }
                      />
                      {label}
                    </label>
                  ))}
                </Card>
                <Card className="grid gap-1">
                  <h2 className="font-semibold">Report cards by level</h2>
                  {(["nursery", "primary", "secondary"] as const).map((l) => (
                    <label key={l} className="flex min-h-11 items-center gap-2">
                      <input
                        type="checkbox"
                        className="size-5"
                        checked={s.levels[l]}
                        onChange={(e) => {
                          setLevelChange({
                            ...s.levels,
                            [l]: e.target.checked,
                          });
                          setAsk("level");
                        }}
                      />
                      {
                        {
                          nursery: "Nursery",
                          primary: "Primary",
                          secondary: "Secondary (Junior and Senior)",
                        }[l]
                      }
                    </label>
                  ))}
                </Card>
              </div>
            ),
          },
          {
            value: "admins",
            label: "School admins",
            content: <Admins schoolId={id} />,
          },
          {
            value: "subscription",
            label: "Subscription",
            content: (
              <Card className="grid max-w-md gap-3">
                <label className="flex min-h-11 items-center gap-2">
                  <input
                    type="checkbox"
                    className="size-5"
                    checked={s.subscription?.billing_enabled ?? false}
                    onChange={(e) =>
                      subscription.mutate({ billing_enabled: e.target.checked })
                    }
                  />
                  Billing
                </label>
                <Field label="Grace period (days)">
                  {(f) => (
                    <Input
                      {...f}
                      inputMode="numeric"
                      value={grace ?? ""}
                      placeholder="Platform default"
                      onChange={(e) => setGrace(e.target.value)}
                    />
                  )}
                </Field>
                <div>
                  <Button
                    disabled={grace === null || !/^\d+$/.test(grace)}
                    onClick={() =>
                      subscription.mutate({ grace_period_days: Number(grace) })
                    }
                  >
                    Save
                  </Button>
                </div>
              </Card>
            ),
          },
          {
            value: "invoices",
            label: "Invoices",
            content: (
              <DataTable
                caption="Invoices"
                rows={invoices.data ?? []}
                rowKey={(i) => i.id}
                empty="No invoices yet."
                columns={[
                  { key: "term", header: "Term", cell: (i) => i.term },
                  {
                    key: "amount",
                    header: "Amount",
                    numeric: true,
                    cell: (i) => money(i.amount_kobo),
                  },
                  { key: "due", header: "Due", cell: (i) => date(i.due_on) },
                  {
                    key: "status",
                    header: "Status",
                    cell: (i) => <StatusBadge status={i.status} />,
                  },
                ]}
              />
            ),
          },
          {
            value: "activity",
            label: "Activity",
            content: (
              <ol className="grid gap-2">
                {(activity.data ?? []).map((a) => (
                  <li key={a.id}>
                    <span className="font-medium">
                      {a.actor_name ?? "SchoolFlow (automatic)"}
                    </span>{" "}
                    <span className="text-muted">{a.action}</span>{" "}
                    <span className="text-sm text-muted">
                      {dateTime(a.created_at)}
                    </span>
                  </li>
                ))}
              </ol>
            ),
          },
        ]}
      />
      <ReasonDialog
        open={ask === "suspend"}
        onOpenChange={(o) => setAsk(o ? "suspend" : null)}
        title={`Suspend ${s.name}?`}
        description="Its people can't log in until you reactivate it. Suspending never deletes data."
        confirmLabel="Suspend school"
        danger
        busy={suspend.isPending}
        onConfirm={(r) => suspend.mutate(r)}
      />
      <ConfirmDialog
        open={ask === "level"}
        onOpenChange={(o) => setAsk(o ? "level" : null)}
        title="Change report cards by level?"
        description="A level that is off disappears from the school's menus, classes and templates, and its requests are refused. Published reports still verify."
        confirmLabel="Save"
        busy={levels.isPending}
        onConfirm={() => levelChange && levels.mutate(levelChange)}
      />
    </>
  );
}
