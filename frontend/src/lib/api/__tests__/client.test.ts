// The API client sends the CSRF header on changes only, and turns a problem
// response (RFC 9457) into an ApiError carrying its code.
import "@/test/setup";

import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";

import { ApiError, CSRF_HEADER, api, ok } from "@/lib/api/client";
import { server } from "@/test/setup";

test("a change carries the CSRF token from its cookie; a read does not", async () => {
  // jsdom refuses __Host- cookies on http, so the cookie is supplied directly.
  vi.spyOn(document, "cookie", "get").mockReturnValue(
    "other=1; __Host-sf_csrf=abc123",
  );
  const seen: Record<string, string | null> = {};
  server.use(
    http.post("*/api/v1/auth/logout", ({ request }) => {
      seen.post = request.headers.get(CSRF_HEADER);
      return new HttpResponse(null, { status: 204 });
    }),
    http.get("*/api/v1/notices/unread-count", ({ request }) => {
      seen.get = request.headers.get(CSRF_HEADER);
      return HttpResponse.json({ unread: 0 });
    }),
  );
  await api.POST("/api/v1/auth/logout");
  await ok(api.GET("/api/v1/notices/unread-count"));
  expect(seen).toEqual({ post: "abc123", get: null });
});

test("a refusal becomes an ApiError with its status and code", async () => {
  server.use(
    http.get("*/api/v1/notices/unread-count", () =>
      HttpResponse.json(
        { title: "Forbidden", code: "permission_denied" },
        { status: 403 },
      ),
    ),
  );
  const failure = await ok(api.GET("/api/v1/notices/unread-count")).catch(
    (error: unknown) => error,
  );
  expect(failure).toBeInstanceOf(ApiError);
  expect(failure).toMatchObject({ status: 403, code: "permission_denied" });
});
