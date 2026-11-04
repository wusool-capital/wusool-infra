import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiKeyGate } from "@/components/ApiKeyGate";
import { Mark } from "@/components/Mark";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getMeQueryKey, useGetMe } from "@/gen/hooks/useGetMe";
import { useGetAuthConfig } from "@/gen/hooks/useGetAuthConfig";
import { onUnauthorized } from "@/lib/api-client";
import { useApiKey } from "@/lib/api-key";
import { CurrentUserContext, signInUrl } from "@/lib/session";

const SIGN_IN_ERRORS: Record<string, string> = {
  denied: "Sign-in was cancelled in Slack.",
  expired: "That sign-in link expired. Try again.",
  wrong_workspace: "Sign in with your Wusool Slack account.",
  failed: "Slack couldn't confirm who you are. Try again.",
};

function signInError(): string | null {
  const code = new URLSearchParams(window.location.search).get("signin_error");
  return code === null
    ? null
    : (SIGN_IN_ERRORS[code] ?? SIGN_IN_ERRORS.failed ?? null);
}

function Screen({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <main className="grid min-h-full place-items-center bg-canvas px-md">
      <div className="flex w-full max-w-[400px] animate-rise flex-col gap-lg">
        <div className="flex flex-col gap-md">
          <Mark className="size-10" />
          <h1 className="font-serif text-title">Wusool Toolkit</h1>
        </div>
        {children}
      </div>
    </main>
  );
}

function SignIn({
  onUseKey,
}: {
  onUseKey: (() => void) | undefined;
}): React.JSX.Element {
  const error = signInError();
  return (
    <Screen>
      <p className="text-lead text-ink-muted">
        Sign in with your Wusool Slack account. Your runs and decisions are
        recorded under your name, as they are in Slack.
      </p>
      {error && (
        <Alert tone="danger">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      )}
      <Button asChild size="lg">
        <a href={signInUrl()}>Sign in with Slack</a>
      </Button>
      {onUseKey && (
        <Button variant="link" className="self-start px-0" onClick={onUseKey}>
          Use an access key instead
        </Button>
      )}
    </Screen>
  );
}

// Who is using the app: a Slack sign-in, or the shared key where the server still allows it.
export function AuthGate({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const key = useApiKey();
  const config = useGetAuthConfig({ query: { staleTime: Infinity } });
  const me = useGetMe({
    query: { queryKey: [...getMeQueryKey(), key], retry: false },
  });
  const [usingKey, setUsingKey] = useState(false);
  const queryClient = useQueryClient();

  // Only a signed-in page resets: a 401 from the sign-in check itself must not loop.
  useEffect(
    () =>
      onUnauthorized(() => {
        const signedIn = queryClient
          .getQueriesData({ queryKey: getMeQueryKey() })
          .some(([, data]) => data !== undefined);
        if (signedIn)
          void queryClient.resetQueries({ queryKey: getMeQueryKey() });
      }),
    [queryClient],
  );

  if (me.isSuccess)
    return (
      <CurrentUserContext.Provider value={me.data}>
        {children}
      </CurrentUserContext.Provider>
    );
  if (me.isPending || config.isPending)
    return (
      <Screen>
        <p className="text-body text-ink-subtle" aria-live="polite">
          Checking your sign-in…
        </p>
      </Screen>
    );
  if (config.isError)
    return (
      <Screen>
        <Alert tone="danger">
          <AlertTitle>
            Couldn't reach the server. Reload to try again.
          </AlertTitle>
        </Alert>
      </Screen>
    );
  const { slack_sign_in: slack, api_key: keyAllowed } = config.data;
  if (slack && !usingKey)
    return (
      <SignIn
        onUseKey={
          keyAllowed
            ? () => {
                setUsingKey(true);
              }
            : undefined
        }
      />
    );
  if (keyAllowed) return <ApiKeyGate>{children}</ApiKeyGate>;
  return (
    <Screen>
      <Alert tone="warning">
        <AlertTitle>The web app isn't enabled on this server yet.</AlertTitle>
      </Alert>
    </Screen>
  );
}
