import { AlertTriangle, ArrowUpRight, RotateCw } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResearchFieldRead } from "@/gen/types/ResearchFieldRead";
import type { ResearchLinkedInRead } from "@/gen/types/ResearchLinkedInRead";
import type { ResearchRead } from "@/gen/types/ResearchRead";
import { relativeTime } from "@/lib/format";

import { fieldLabel } from "./research-labels";
import { conflictingFields, useResearch } from "./useResearch";

// Below this, a proposal starts unticked: the advisor opts in rather than out.
const AUTO_TICK_CONFIDENCE = 0.8;
function isLink(text: string): boolean {
  return /^https?:\/\//.test(text);
}

function linkClass(): string {
  return "inline-flex items-center gap-[2px] text-ink underline decoration-hairline-tertiary underline-offset-4 hover:decoration-ink";
}

function FieldValue({
  field,
}: {
  field: ResearchFieldRead;
}): React.JSX.Element {
  return isLink(field.display) ? (
    <a
      href={field.display}
      target="_blank"
      rel="noreferrer noopener"
      className={`${linkClass()} break-all`}
    >
      {field.display}
    </a>
  ) : (
    <span className="break-words">{field.display}</span>
  );
}

function FieldRow({
  field,
  checked,
  conflict,
  disabled,
  onToggle,
}: {
  field: ResearchFieldRead;
  checked: boolean;
  conflict: boolean;
  disabled: boolean;
  onToggle: () => void;
}): React.JSX.Element {
  const id = `research-field-${field.name}`;
  return (
    <li className="grid grid-cols-[20px_minmax(0,1fr)] gap-x-sm gap-y-xxs border-b border-hairline px-sm py-sm last:border-b-0">
      {field.saved ? (
        <span aria-hidden className="pt-[3px] text-small text-success">
          ✓
        </span>
      ) : (
        <input
          id={id}
          type="checkbox"
          className="mt-[3px] size-4 accent-primary"
          checked={checked}
          disabled={disabled}
          aria-describedby={`${id}-meta`}
          onChange={onToggle}
        />
      )}
      <div className="flex min-w-0 flex-col gap-xxs">
        <div className="flex flex-wrap items-baseline justify-between gap-x-sm text-small text-ink-subtle">
          <label htmlFor={field.saved ? undefined : id}>
            {fieldLabel(field.name)}
          </label>
          <span className="tabular-nums">
            {field.saved
              ? "Saved to Attio"
              : `${String(Math.round(field.confidence * 100))}% confident`}
          </span>
        </div>
        <p className="text-body text-ink">
          <FieldValue field={field} />
        </p>
        <div
          id={`${id}-meta`}
          className="flex flex-wrap items-baseline gap-x-sm text-small text-ink-subtle"
        >
          {conflict && (
            <span className="text-danger">
              Filled in since the research ran
            </span>
          )}
          {isLink(field.source_url) && (
            <a
              href={field.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className={linkClass()}
            >
              Source <ArrowUpRight aria-hidden className="size-3" />
            </a>
          )}
        </div>
        <details className="text-small text-ink-subtle">
          <summary className="cursor-pointer select-none hover:text-ink">
            Why
          </summary>
          <p className="pt-xxs text-body text-ink-muted">{field.rationale}</p>
        </details>
      </div>
    </li>
  );
}

function LinkedIn({
  linkedin,
  orgName,
}: {
  linkedin: ResearchLinkedInRead;
  orgName: string;
}): React.JSX.Element {
  let body: React.ReactNode;
  if (linkedin.outcome === "failed")
    body = (
      <p className="text-body text-ink-subtle">The LinkedIn scan failed.</p>
    );
  else if (linkedin.outcome === "skipped")
    body = (
      <p className="text-body text-ink-subtle">
        No LinkedIn page is saved for {orgName}.
      </p>
    );
  else
    body = (
      <>
        {linkedin.job_changes.length > 0 && (
          <ul className="flex flex-col gap-xs">
            {linkedin.job_changes.map((change) => (
              <li key={change.source_url} className="text-body text-ink">
                <a
                  href={change.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className={linkClass()}
                >
                  {change.name}
                </a>{" "}
                <span className="text-ink-muted">
                  is now {change.title ?? "in a new role"}
                  {change.company ? ` at ${change.company}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
        {linkedin.posts.length > 0 ? (
          <ul className="flex flex-col rounded-md border border-hairline">
            {linkedin.posts.map((post) => (
              <li
                key={post.url}
                className="flex flex-col gap-xxs border-b border-hairline px-sm py-sm last:border-b-0"
              >
                <span className="text-small text-ink-subtle">
                  {post.author_name ?? orgName}
                  {post.posted_at && ` · ${relativeTime(post.posted_at)}`}
                </span>
                <p className="line-clamp-3 text-body text-ink">{post.text}</p>
                <a
                  href={post.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className={`${linkClass()} self-start text-small`}
                >
                  Open post <ArrowUpRight aria-hidden className="size-3" />
                </a>
              </li>
            ))}
          </ul>
        ) : (
          linkedin.job_changes.length === 0 && (
            <p className="text-body text-ink-subtle">
              No new posts in the past month.
            </p>
          )
        )}
        {linkedin.contacts_without_linkedin > 0 && (
          <p className="text-small text-ink-subtle">
            {linkedin.contacts_without_linkedin} contact
            {linkedin.contacts_without_linkedin === 1 ? " has" : "s have"} no
            LinkedIn URL on file.
          </p>
        )}
      </>
    );
  return (
    <section
      aria-labelledby="research-linkedin"
      className="flex flex-col gap-xs"
    >
      <h5 id="research-linkedin" className="text-small text-ink-subtle">
        LinkedIn
      </h5>
      {body}
    </section>
  );
}

function Placeholder(): React.JSX.Element {
  return (
    <ul aria-hidden className="flex flex-col rounded-md border border-hairline">
      {[0, 1, 2].map((row) => (
        <li
          key={row}
          className="flex flex-col gap-xs border-b border-hairline px-sm py-sm last:border-b-0"
        >
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-5 w-3/4" />
        </li>
      ))}
    </ul>
  );
}

// Full research on an approved discovered seller: what to add to Attio, and LinkedIn.
export function ResearchBlock({
  runId,
  candidateId,
  orgName,
  research,
}: {
  runId: string;
  candidateId: string;
  orgName: string;
  research: ResearchRead | null;
}): React.JSX.Element {
  const action = useResearch(runId, candidateId);
  const unsaved = research?.fields.filter((f) => !f.saved) ?? [];
  const savedCount = (research?.fields.length ?? 0) - unsaved.length;
  const [ticked, setTicked] = useState<Set<string>>(
    () =>
      new Set(
        unsaved
          .filter((f) => f.confidence >= AUTO_TICK_CONFIDENCE)
          .map((f) => f.name),
      ),
  );
  const conflicts = conflictingFields(action.error);
  const chosen = unsaved.filter((f) => ticked.has(f.name));
  const busy = action.isPending;
  const failure =
    action.isError && conflicts.length === 0 ? action.error.message : null;

  const toggle = (name: string): void => {
    setTicked((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  let body: React.ReactNode;
  if (research === null)
    body = (
      <div className="flex flex-col items-start gap-xs">
        <p className="text-body text-ink-subtle">
          Full research hasn't run for this seller yet.
        </p>
        <Button
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() => {
            action.mutate({ kind: "retry" });
          }}
        >
          {busy ? "Starting…" : "Run full research"}
        </Button>
        {failure && <p className="text-body text-danger">{failure}</p>}
      </div>
    );
  else if (research.status === "running")
    body = (
      <>
        <p aria-live="polite" className="text-body text-ink-muted">
          Researching {orgName}… Its website, company data and LinkedIn, usually
          under a minute.
        </p>
        <Placeholder />
      </>
    );
  else if (research.status === "failed")
    body = (
      <Alert tone="danger">
        <AlertTriangle aria-hidden />
        <AlertTitle>{research.error ?? "Research didn't finish."}</AlertTitle>
        <AlertDescription>
          <Button
            size="sm"
            variant="secondary"
            className="mt-xs"
            disabled={busy}
            onClick={() => {
              action.mutate({ kind: "retry" });
            }}
          >
            <RotateCw aria-hidden />
            {busy ? "Starting…" : "Try again"}
          </Button>
        </AlertDescription>
      </Alert>
    );
  else if (research.fields.length === 0)
    body = (
      <p className="text-body text-ink-subtle">
        Research found nothing to add beyond what discovery saved.
      </p>
    );
  else
    body = (
      <form
        className="flex flex-col gap-sm"
        onSubmit={(event) => {
          event.preventDefault();
          if (chosen.length === 0 || busy || research.reviewed) return;
          action.mutate(
            { kind: "save", fields: chosen.map((f) => f.name) },
            {
              onError: (error) => {
                const filled = conflictingFields(error);
                if (filled.length > 0)
                  setTicked(
                    (current) =>
                      new Set([...current].filter((n) => !filled.includes(n))),
                  );
              },
            },
          );
        }}
      >
        <fieldset className="flex flex-col gap-xs">
          <legend className="sr-only">Fields to save to Attio</legend>
          <ul className="flex flex-col rounded-md border border-hairline">
            {research.fields.map((field) => (
              <FieldRow
                key={field.name}
                field={field}
                // A save or a skip is final, so the list locks after either.
                checked={!research.reviewed && ticked.has(field.name)}
                conflict={conflicts.includes(field.name)}
                disabled={busy || research.reviewed}
                onToggle={() => {
                  toggle(field.name);
                }}
              />
            ))}
          </ul>
        </fieldset>
        <div aria-live="polite">
          {conflicts.length > 0 && (
            <p className="text-body text-danger">
              Someone filled in {conflicts.map(fieldLabel).join(", ")} since the
              research ran. They're unticked; save the rest.
            </p>
          )}
          {failure && <p className="text-body text-danger">{failure}</p>}
        </div>
        {research.reviewed ? (
          <p role="status" className="text-body text-ink-muted">
            {savedCount > 0
              ? `Saved ${String(savedCount)} field${savedCount === 1 ? "" : "s"} to Attio.`
              : "Skipped. Nothing was saved to Attio."}
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-xs">
            <Button type="submit" disabled={busy || chosen.length === 0}>
              {busy && action.variables.kind === "save"
                ? "Saving…"
                : `Save ${String(chosen.length)} field${chosen.length === 1 ? "" : "s"} to Attio`}
            </Button>
            <Button
              type="button"
              variant="tertiary"
              disabled={busy}
              onClick={() => {
                action.mutate({ kind: "skip" });
              }}
            >
              Skip
            </Button>
          </div>
        )}
      </form>
    );

  return (
    <section
      aria-labelledby={`research-${candidateId}`}
      aria-busy={research?.status === "running"}
      className="flex flex-col gap-md border-t border-hairline pt-md"
    >
      <h4
        id={`research-${candidateId}`}
        className="text-body font-medium text-ink"
      >
        Full research
      </h4>
      {body}
      {research?.linkedin ? (
        <LinkedIn linkedin={research.linkedin} orgName={orgName} />
      ) : (
        research?.status === "running" && (
          <section aria-hidden className="flex flex-col gap-xs">
            <span className="text-small text-ink-subtle">LinkedIn</span>
            <Skeleton className="h-5 w-1/2" />
          </section>
        )
      )}
    </section>
  );
}
