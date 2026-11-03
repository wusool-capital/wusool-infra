import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiRequestError } from "@/lib/api-client";
import { setApiKey, useApiKey } from "@/lib/api-key";
import { searchBuyers } from "@/gen/clients/searchBuyers";

const schema = z.object({
  key: z.string().trim().min(1, "Enter the access key."),
});
type FormValues = z.infer<typeof schema>;

async function verify(key: string): Promise<string | null> {
  setApiKey(key);
  try {
    // Any authenticated call proves the key; this one is cheap and read-only.
    await searchBuyers({ query: { q: "zz" } });
    return null;
  } catch (error) {
    setApiKey(null);
    if (error instanceof ApiRequestError && error.status === 503) {
      return "The web app isn't enabled on this server yet.";
    }
    if (error instanceof ApiRequestError && error.status === 401) {
      return "That key wasn't accepted.";
    }
    return "Couldn't reach the server. Try again.";
  }
}

export function ApiKeyGate({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const key = useApiKey();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { key: "" },
  });

  if (key !== null) return <>{children}</>;

  const fieldError = form.formState.errors.key?.message ?? serverError;
  return (
    <main className="grid min-h-full place-items-center bg-canvas px-md">
      <form
        noValidate
        onSubmit={(event) => {
          void form.handleSubmit(async ({ key: value }) => {
            setServerError(await verify(value));
          })(event);
        }}
        className="flex w-full max-w-[400px] flex-col gap-lg rounded-lg border border-hairline bg-surface-1 p-lg"
      >
        <div className="flex flex-col gap-xs">
          <h1 className="text-card-title text-balance">Wusool Toolkit</h1>
          <p className="text-body-sm text-ink-subtle">
            Enter the team access key to use the web tools. It's kept for this
            tab only.
          </p>
        </div>
        <div className="flex flex-col gap-xs">
          <Label htmlFor="api-key">Access key</Label>
          <Input
            id="api-key"
            type="password"
            autoComplete="current-password"
            autoFocus
            aria-invalid={fieldError !== null}
            aria-describedby={fieldError ? "api-key-error" : undefined}
            {...form.register("key", {
              onChange: () => {
                setServerError(null);
              },
            })}
          />
          {fieldError && (
            <p id="api-key-error" className="text-caption text-danger">
              {fieldError}
            </p>
          )}
        </div>
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Checking…" : "Use this key"}
        </Button>
      </form>
    </main>
  );
}
