"use client";

// Reading and changing data with the same habits everywhere: a change shows a
// toast, refreshes the lists it touched, and turns a refusal into plain words.
import {
  type QueryKey,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError } from "@/lib/api/client";

export function useApi<T>(key: QueryKey, fn: () => Promise<T>, enabled = true) {
  return useQuery({ queryKey: key, queryFn: fn, enabled });
}

// Plain words for the problem codes people can meet on admin pages.
const MESSAGES: Record<string, string> = {
  name_taken: "That name is already used.",
  username_taken: "That username is already used.",
  email_taken: "That email is already used.",
  admission_number_taken: "That admission number is already used.",
  permission_denied: "You don't have permission to do this.",
  feature_disabled: "This feature is switched off for your school.",
  level_disabled: "Report cards for this level are switched off.",
  admin_limit: "You have no school admin places left.",
  structure_locked:
    "Scores have been entered this term, so this can't change now.",
  in_use: "It is in use, so it can't be removed.",
  no_active_term: "Activate a term first.",
};

export function problemText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code && MESSAGES[error.code]) return MESSAGES[error.code]!;
    if (error.status === 422)
      return "Some details are missing or not valid. Check the form and try again.";
    return error.detail ?? error.message;
  }
  return "Something went wrong. Try again.";
}

type ActionOptions<T> = {
  invalidate?: QueryKey[];
  done?: string | ((result: T) => string | null);
  onDone?: (result: T) => void;
};

export function useAction<A, T>(
  fn: (args: A) => Promise<T>,
  options: ActionOptions<T> = {},
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async (result) => {
      await Promise.all(
        (options.invalidate ?? []).map((key) =>
          client.invalidateQueries({ queryKey: key }),
        ),
      );
      const message =
        typeof options.done === "function"
          ? options.done(result)
          : options.done;
      if (message) toast.success(message);
      options.onDone?.(result);
    },
    onError: (error) => {
      toast.error(problemText(error));
    },
  });
}
