// The typed API client (D-001, D-015). Types come from the backend's OpenAPI
// description (`bun run api:types`), so a wrong path or field fails `tsc`.
// Same domain as the API, so the session cookie goes with every request; the
// CSRF header is copied from the CSRF cookie on every change (D-038).
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "@/lib/api/schema";

export const CSRF_COOKIE = "__Host-sf_csrf";
export const CSRF_HEADER = "X-CSRF-Token";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly detail: string | null;

  constructor(
    status: number,
    problem: { title?: string; code?: string; detail?: string } | null,
  ) {
    super(problem?.title ?? `Request failed (${status})`);
    this.status = status;
    this.code = problem?.code ?? null;
    this.detail = problem?.detail ?? null;
  }
}

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const found = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${name}=`));
  return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
}

const csrf: Middleware = {
  onRequest({ request }) {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      request.headers.set(CSRF_HEADER, readCookie(CSRF_COOKIE));
    }
    return request;
  },
};

function baseUrl(): string {
  // In the browser, same origin; in tests (no window location), a fixed origin.
  return typeof window !== "undefined" && window.location.origin !== "null"
    ? window.location.origin
    : "http://localhost";
}

export const api = createClient<paths>({
  baseUrl: baseUrl(),
  credentials: "same-origin",
  // Looked up on each call (not kept from start-up), so the browser's fetch is always the current one.
  fetch: (request: Request) => globalThis.fetch(request),
});
api.use(csrf);

type Result<T> = { data?: T; error?: unknown; response: Response };

// Turns an openapi-fetch result into data or a thrown ApiError with the problem's code.
export async function ok<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) {
    throw new ApiError(
      response.status,
      (error ?? null) as { title?: string; code?: string } | null,
    );
  }
  return data as T;
}
