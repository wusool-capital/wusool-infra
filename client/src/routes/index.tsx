import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: () => <h1 className="p-lg text-headline">Wusool Toolkit</h1>,
});
