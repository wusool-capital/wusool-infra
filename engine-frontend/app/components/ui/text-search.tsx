import { MagnifyingGlass } from "@phosphor-icons/react";
import { useState } from "react";
import { useSearchParams } from "react-router";

/**
 * A plain text search for lists already loaded in the page: it filters as you type (no Apply,
 * no AI) and keeps the words in the URL so a filtered view can be shared.
 */
export function TextSearch({ label, placeholder }: { label: string; placeholder: string }) {
  const [params, setParams] = useSearchParams();
  const [value, setValue] = useState(params.get("q") ?? "");

  const update = (next: string) => {
    setValue(next);
    setParams(
      (url) => {
        if (next.trim()) url.set("q", next);
        else url.delete("q");
        return url;
      },
      // Typing should not add a history entry per letter.
      { replace: true, preventScrollReset: true },
    );
  };

  return (
    <label className="text-search">
      <MagnifyingGlass size={16} aria-hidden="true" />
      <span className="visually-hidden">{label}</span>
      <input type="search" placeholder={placeholder} value={value} onChange={(event) => update(event.target.value)} />
    </label>
  );
}
