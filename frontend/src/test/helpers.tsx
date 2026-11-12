// Rendering with the real providers, and fictional signed-in people.
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";

import { makeQueryClient } from "@/components/providers";
import type { Me } from "@/lib/api/types";
import { server } from "@/test/setup";

export function renderWithClient(ui: ReactElement) {
  const client = makeQueryClient();
  return {
    client,
    ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>),
  };
}

const ALL_FEATURES = [
  "results",
  "report_cards",
  "parent_portal",
  "correction_queue",
  "notice_board",
  "email_notifications",
];

export function makeMe(changes: Partial<Me> = {}): Me {
  return {
    user: {
      id: "u1",
      full_name: "Ngozi Okeke",
      username: "ngozi.okeke",
      email: "ngozi.okeke@gmc.example",
    },
    school: {
      id: "s1",
      code: "GMC",
      name: "Greenfield Model College",
      colour: "#1E6B45",
    },
    schools: [],
    role: "school_admin",
    is_primary: true,
    is_super_admin: false,
    must_change_password: false,
    permissions: [],
    features: ALL_FEATURES,
    form_class: null,
    unread_notices: 3,
    ...changes,
  };
}

export function signedIn(me: Me | null) {
  server.use(
    http.get("*/api/v1/auth/me", () =>
      me
        ? HttpResponse.json(me)
        : HttpResponse.json(
            { title: "Not signed in", code: "not_signed_in" },
            { status: 401 },
          ),
    ),
    http.get("*/api/v1/notices/unread-count", () =>
      HttpResponse.json({ unread: me?.unread_notices ?? 0 }),
    ),
  );
}
