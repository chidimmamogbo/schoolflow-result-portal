"use client";

// Who is signed in, from GET /auth/me (D-160). Guards here only steer the user
// to the right page; the server refuses anything the person may not do.
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, ok } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

export const ME_KEY = ["me"] as const;

export type Role =
  | "super_admin"
  | "school_admin"
  | "reviewer"
  | "teacher"
  | "parent"
  | "student";

export function roleOf(me: Me): Role {
  return me.is_super_admin ? "super_admin" : (me.role as Role);
}

export async function fetchMe(): Promise<Me | null> {
  try {
    return await ok(api.GET("/api/v1/auth/me"));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function useMe() {
  return useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: 30_000 });
}

// Each role's home page after login.
export function homeFor(me: Me): string {
  if (me.must_change_password) return "/change-password";
  switch (roleOf(me)) {
    case "super_admin":
      return "/platform";
    case "school_admin":
      return "/school/dashboard";
    case "reviewer":
      return "/review";
    case "teacher":
      return "/teacher";
    case "parent":
      return "/parent";
    case "student":
      return "/student";
  }
}

export function useLogout() {
  const client = useQueryClient();
  return async () => {
    try {
      await api.POST("/api/v1/auth/logout");
    } finally {
      client.setQueryData(ME_KEY, null);
      client.clear();
    }
  };
}

export function can(me: Me, permission: string): boolean {
  return me.permissions.includes(permission);
}

export function featureOn(me: Me, feature: string): boolean {
  return me.features.includes(feature);
}
