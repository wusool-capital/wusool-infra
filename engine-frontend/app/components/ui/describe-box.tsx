import { useState } from "react";

// initial: the last sentence, kept in the URL (`ask`) so it is still there when you come back.
type Props = { label: string; placeholder: string; initial?: string; onSubmit: (text: string) => void };

/**
 * One sentence that fills the filters beside it and runs the search on Enter
 * (Search, Multiples). The placeholder says what to type; the filled filters
 * light up so the person sees what changed and can adjust them.
 */
export function DescribeBox({ label, placeholder, initial = "", onSubmit }: Props) {
  const [text, setText] = useState(initial);

  return (
    <label className="describe">
      <span className="visually-hidden">{label}</span>
      <input
        type="search"
        placeholder={placeholder}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && text.trim() && onSubmit(text.trim())}
      />
    </label>
  );
}
