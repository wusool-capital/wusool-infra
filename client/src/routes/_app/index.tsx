import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowUp } from "lucide-react";
import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/ui/button";
import { TOOLS } from "@/features/tools";

export const Route = createFileRoute("/_app/")({
  component: HomePage,
});

function HomePage(): React.JSX.Element {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const trimmed = query.trim();

  return (
    <>
      <TopBar crumbs={[{ label: "Tools" }]} />
      <main className="mx-auto flex w-full max-w-[1100px] flex-col gap-xxl px-md py-xxl md:px-xl">
        <section
          aria-labelledby="home-title"
          className="mx-auto flex w-full max-w-[680px] flex-col gap-lg"
        >
          <h1 id="home-title" className="text-center text-headline">
            Which buyer are we matching?
          </h1>
          <form
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              if (trimmed.length < 2) return;
              void navigate({ to: "/find-match", search: { q: trimmed } });
            }}
            className="flex items-end gap-sm rounded-lg border border-hairline bg-surface-1 p-sm focus-within:border-hairline-strong"
          >
            <label htmlFor="home-buyer" className="sr-only">
              Buyer name
            </label>
            <input
              id="home-buyer"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
              }}
              placeholder="Type a buyer's name to start a find-match run"
              autoComplete="off"
              className="min-h-11 flex-1 bg-transparent px-xs text-body text-ink outline-none placeholder:text-ink-subtle"
            />
            <Button
              type="submit"
              size="icon"
              aria-label="Find matches"
              disabled={trimmed.length < 2}
            >
              <ArrowUp aria-hidden />
            </Button>
          </form>
        </section>

        <section aria-labelledby="tools-title" className="flex flex-col gap-md">
          <h2 id="tools-title" className="text-body font-medium">
            Tools
          </h2>
          <ul className="grid grid-cols-1 gap-md md:grid-cols-2 xl:grid-cols-3">
            {TOOLS.map((tool) => (
              <li
                key={tool.id}
                aria-disabled={tool.web ? undefined : true}
                className={
                  tool.web
                    ? "flex flex-col gap-md rounded-lg border border-hairline-strong bg-surface-2 p-lg"
                    : "flex flex-col gap-md rounded-lg border border-hairline bg-surface-1 p-lg"
                }
              >
                <div className="flex items-start justify-between gap-sm">
                  <h3
                    className={
                      tool.web
                        ? "text-body font-medium text-ink"
                        : "text-body font-medium text-ink-muted"
                    }
                  >
                    {tool.name}
                  </h3>
                  {!tool.web && <StatusBadge status="coming_soon" />}
                </div>
                <p className="flex-1 text-body-sm text-ink-subtle">
                  {tool.description}
                </p>
                {tool.web ? (
                  <Button asChild variant="secondary" className="self-start">
                    <Link to="/find-match">Start a run</Link>
                  </Button>
                ) : (
                  <p className="text-caption text-ink-subtle">
                    In Slack:{" "}
                    <code className="font-mono text-mono">
                      {tool.slackCommand}
                    </code>
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}
