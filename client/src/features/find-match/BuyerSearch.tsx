import { useId, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSearchBuyers } from "@/gen/hooks/useSearchBuyers";
import type { BuyerSummary } from "@/gen/types/BuyerSummary";
import { useDebounced } from "@/hooks/useDebounced";
import { cn } from "@/lib/utils";

const MIN_CHARS = 2;

function buyerMeta(buyer: BuyerSummary): string {
  return [
    buyer.target_vertical,
    buyer.organization.hq_country,
    buyer.model,
    buyer.mandate_status,
  ]
    .filter(
      (part): part is string => typeof part === "string" && part.length > 0,
    )
    .join(" · ");
}

export function BuyerSearch({
  initialQuery,
  onPick,
}: {
  initialQuery: string;
  onPick: (buyer: BuyerSummary) => void;
}): React.JSX.Element {
  const listId = useId();
  const [query, setQuery] = useState(initialQuery);
  const [highlight, setHighlight] = useState(0);
  const term = useDebounced(query.trim(), 250);
  const enabled = term.length >= MIN_CHARS;
  const search = useSearchBuyers(
    { query: { q: term } },
    { query: { enabled } },
  );
  const results = enabled ? (search.data ?? []) : [];
  const active = results[Math.min(highlight, results.length - 1)];

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
    if (results.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((i) => Math.min(i + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && active !== undefined) {
      event.preventDefault();
      onPick(active);
    }
  };

  return (
    <div className="flex flex-col gap-sm">
      <Label htmlFor={`${listId}-input`}>Buyer</Label>
      <Input
        id={`${listId}-input`}
        role="combobox"
        aria-expanded={results.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active ? `${listId}-${active.id}` : undefined}
        autoComplete="off"
        autoFocus
        name="buyer-search"
        placeholder="Search buyers by organization name…"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setHighlight(0);
        }}
        onKeyDown={onKeyDown}
      />

      {!enabled && (
        <p className="text-caption text-ink-subtle">
          Type at least {MIN_CHARS} letters.
        </p>
      )}

      {enabled && search.isPending && (
        <div aria-hidden className="flex flex-col gap-xxs">
          {[0, 1, 2].map((row) => (
            <div
              key={row}
              className="flex flex-col gap-xs rounded-md px-sm py-sm"
            >
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-72 max-w-full" />
            </div>
          ))}
        </div>
      )}

      {enabled && search.isError && (
        <div
          role="alert"
          className="flex items-center gap-sm text-body-sm text-ink-muted"
        >
          Couldn't search buyers.
          <Button
            variant="link"
            onClick={() => {
              void search.refetch();
            }}
          >
            Retry
          </Button>
        </div>
      )}

      {enabled && search.isSuccess && results.length === 0 && (
        <p className="text-body-sm text-ink-subtle">
          No buyer matches “{term}”. Try a shorter name.
        </p>
      )}

      <ul
        id={listId}
        role="listbox"
        aria-label="Matching buyers"
        className="flex flex-col gap-[2px]"
      >
        {results.map((buyer, index) => {
          const meta = buyerMeta(buyer);
          return (
            <li
              key={buyer.id}
              id={`${listId}-${buyer.id}`}
              role="option"
              aria-selected={index === highlight}
              onMouseEnter={() => {
                setHighlight(index);
              }}
              onClick={() => {
                onPick(buyer);
              }}
              className={cn(
                "flex cursor-pointer flex-col gap-[2px] rounded-md px-sm py-xs",
                index === highlight ? "bg-surface-3" : "hover:bg-surface-2",
              )}
            >
              <span className="text-body-sm text-ink">
                {buyer.organization.name}
              </span>
              <span className="text-caption text-ink-subtle">
                {meta || "No mandate details yet"}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
