type Props = {
  legend: string;
  options: string[];
  picked: string[];
  onToggle: (value: string) => void;
  disabled?: boolean;
};

/** A checklist. A long one scrolls inside its own box so it does not push the form down. */
export function CheckGroup({ legend, options, picked, onToggle, disabled = false }: Props) {
  return (
    <fieldset className={options.length > 12 ? "check-group check-group--scroll" : "check-group"}>
      <legend>{legend}</legend>
      {options.map((value) => (
        <label key={value} className="check-group__option">
          <input type="checkbox" checked={picked.includes(value)} disabled={disabled} onChange={() => onToggle(value)} />
          {value}
        </label>
      ))}
    </fieldset>
  );
}
