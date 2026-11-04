import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext } from "react";

import { logout } from "@/gen/clients/logout";
import { getMeQueryKey } from "@/gen/hooks/useGetMe";
import type { MeResponse } from "@/gen/types/MeResponse";
import { setApiKey } from "@/lib/api-key";

export const CurrentUserContext = createContext<MeResponse | null>(null);

// Null only while the shared-key fallback is still being confirmed.
export function useCurrentUser(): MeResponse | null {
  return useContext(CurrentUserContext);
}

export function displayName(user: MeResponse | null): string {
  if (user === null || user.via === "key") return "Shared access key";
  return user.name ?? user.slack_user_id ?? "Signed in";
}

export function useSignOut(): () => Promise<void> {
  const queryClient = useQueryClient();
  return async () => {
    await logout().catch(() => undefined);
    setApiKey(null);
    queryClient.removeQueries({ queryKey: getMeQueryKey() });
    await queryClient.invalidateQueries({ queryKey: getMeQueryKey() });
  };
}

export function signInUrl(): string {
  const next = `${window.location.pathname}${window.location.search}`;
  return `/api/auth/slack/login?next=${encodeURIComponent(next)}`;
}
