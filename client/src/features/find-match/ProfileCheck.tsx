import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, CircleCheck } from "lucide-react";
import { useForm } from "react-hook-form";
import type { z } from "zod";

import { CopyErrorButton } from "@/components/CopyErrorButton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { usePreflight } from "@/gen/hooks/usePreflight";
import type { BuyerSummary } from "@/gen/types/BuyerSummary";
import type { PreflightResponse } from "@/gen/types/PreflightResponse";
import { preflightRequestSchema } from "@/gen/zod/preflightRequestSchema";

import { CRITERION_LABELS, contextLines } from "./context-reading";

type FormValues = z.input<typeof preflightRequestSchema>;

function CheckResult({
  result,
  buyerName,
}: {
  result: PreflightResponse;
  buyerName: string;
}): React.JSX.Element {
  const reading = contextLines(result.context);
  const clear = result.conflicts.length === 0 && result.missing.length === 0;
  return (
    <div className="flex flex-col gap-sm" aria-live="polite">
      {result.conflicts.length > 0 && (
        <Alert tone="warning">
          <AlertTriangle aria-hidden />
          <AlertTitle>{buyerName}'s profile doesn't match your note</AlertTitle>
          <AlertDescription>
            <ul className="flex flex-col gap-xxs">
              {result.conflicts.map((d) => (
                <li key={d.criterion}>
                  {CRITERION_LABELS[d.criterion]}: profile has {d.stored}, you
                  said {d.stated ?? "—"}. Your note wins for this run.
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {result.missing.length > 0 && (
        <Alert tone="warning">
          <AlertTriangle aria-hidden />
          <AlertTitle>Missing from {buyerName}'s profile</AlertTitle>
          <AlertDescription>
            <p>
              {result.missing
                .map((d) => CRITERION_LABELS[d.criterion])
                .join(", ")}
              .
            </p>
            <p className="text-ink-subtle">
              Fill these in with <code translate="no">/edit-buyer</code> in
              Slack for a sharper match, or run it now.
            </p>
          </AlertDescription>
        </Alert>
      )}
      {!result.context_checked && (
        <Alert tone="warning">
          <AlertTriangle aria-hidden />
          <AlertTitle>Your note couldn't be checked for conflicts</AlertTitle>
          <AlertDescription>The match still applies it.</AlertDescription>
        </Alert>
      )}
      {clear && result.context_checked && (
        <Alert tone="success">
          <CircleCheck aria-hidden />
          <AlertTitle>
            No missing or conflicting details for {buyerName}
          </AlertTitle>
        </Alert>
      )}
      {reading.length > 0 && (
        <div className="flex flex-col gap-xxs rounded-lg border border-hairline bg-surface-1 px-md py-sm">
          <p className="text-small text-ink-subtle">Read from your note</p>
          <ul className="flex flex-col gap-xxs text-body text-ink-muted">
            {reading.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function ProfileCheck({
  buyer,
  starting,
  startError,
  onRun,
}: {
  buyer: BuyerSummary;
  starting: boolean;
  startError: string | null;
  onRun: (advisorContext: string | null) => void;
}): React.JSX.Element {
  const preflight = usePreflight();
  const form = useForm<FormValues>({
    resolver: zodResolver(preflightRequestSchema),
    defaultValues: { advisor_context: "" },
  });
  const note = (): string | null => {
    const value = (form.getValues("advisor_context") ?? "").trim();
    return value.length > 0 ? value : null;
  };
  const fieldError = form.formState.errors.advisor_context?.message;
  const checked = preflight.isSuccess || preflight.isError;

  return (
    <form
      noValidate
      className="flex flex-col gap-md"
      onSubmit={(event) => {
        void form.handleSubmit(() => {
          preflight.mutate({
            path: { buyer_role_id: buyer.id },
            body: { advisor_context: note() },
          });
        })(event);
      }}
    >
      <div className="flex flex-col gap-xs">
        <Label htmlFor="advisor-context">
          Your note on what {buyer.organization.name} wants (optional)
        </Label>
        <Textarea
          id="advisor-context"
          placeholder="e.g. Healthcare clinics in the GCC, ticket $5–20M, EBITDA above $2M…"
          aria-invalid={fieldError !== undefined}
          aria-describedby="advisor-context-help"
          {...form.register("advisor_context", {
            onChange: () => {
              preflight.reset();
            },
          })}
        />
        <p
          id="advisor-context-help"
          className={
            fieldError ? "text-small text-danger" : "text-small text-ink-subtle"
          }
        >
          {fieldError ??
            "Anything you state here overrides the CRM for this run."}
        </p>
      </div>

      <div className="flex flex-wrap gap-xs">
        {checked ? (
          <Button
            type="button"
            size="lg"
            disabled={starting}
            onClick={() => {
              onRun(note());
            }}
          >
            {starting ? "Starting…" : "Run match"}
          </Button>
        ) : (
          <Button type="submit" size="lg" disabled={preflight.isPending}>
            {preflight.isPending ? "Checking profile…" : "Check profile"}
          </Button>
        )}
        {checked && (
          // A buyer fixed with /edit-buyer meanwhile is only seen by checking again, as Slack does after an edit.
          <Button
            type="submit"
            size="lg"
            variant="tertiary"
            disabled={starting}
          >
            Check again
          </Button>
        )}
      </div>
      {preflight.isSuccess && (
        <CheckResult
          result={preflight.data}
          buyerName={buyer.organization.name}
        />
      )}
      {preflight.isError && (
        <Alert tone="warning">
          <AlertTriangle aria-hidden />
          <AlertTitle>Couldn't check this buyer's profile</AlertTitle>
          <AlertDescription>
            Missing or conflicting details may not be shown. You can still run
            the match.
          </AlertDescription>
        </Alert>
      )}
      {startError && (
        <Alert tone="danger" className="pr-[120px]">
          <AlertTriangle aria-hidden />
          <AlertTitle>Couldn't start the run</AlertTitle>
          <AlertDescription>{startError}</AlertDescription>
          <CopyErrorButton
            message={startError}
            className="absolute top-xs right-xs"
          />
        </Alert>
      )}
    </form>
  );
}
