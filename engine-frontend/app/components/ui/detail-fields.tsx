import type { DetailValue, FieldDef } from "../../demo/types";
import { AmountInput } from "./amount-input";
import { CheckGroup } from "./check-group";

type Props = {
  fields: FieldDef[];
  values: Record<string, DetailValue | undefined>;
  onChange: (key: string, value: DetailValue | undefined) => void;
  /** "Buyer" or "Seller": names the group of fields on the role itself. */
  roleName: string;
  status: "loading" | "ready" | "failed";
};

const GROUPS = [
  { group: "role", heading: (roleName: string) => `${roleName} details` },
  { group: "company", heading: () => "Company details" },
] as const;

const asText = (value: DetailValue | undefined) => (typeof value === "string" ? value : "");
const asNumber = (value: DetailValue | undefined) => (typeof value === "number" ? value : undefined);
const asList = (value: DetailValue | undefined) => (Array.isArray(value) ? value : []);

/**
 * Draws every field the Toolkit lists by its kind: a select or checklist from the field's own
 * options, an amount, a date, yes or no, or text. Nothing here names a field.
 */
export function DetailFields({ fields, values, onChange, roleName, status }: Props) {
  if (fields.length === 0) return null;
  if (status !== "ready") {
    return <p className="muted">{status === "loading" ? "Loading the other fields…" : "Could not load the other fields."}</p>;
  }
  return (
    <>
      {GROUPS.map(({ group, heading }) => {
        const inGroup = fields.filter((field) => field.group === group);
        if (inGroup.length === 0) return null;
        const wide = inGroup.filter((field) => field.kind === "multiline" || field.kind === "multi_select");
        const narrow = inGroup.filter((field) => !wide.includes(field));
        return (
          <section key={group} className="drawer__section">
            <h3 className="panel-heading">{heading(roleName)}</h3>
            <div className="form-grid">
              {narrow.map((field) => (
                <div className="field" key={field.key}>
                  <label htmlFor={`detail-${field.key}`}>{field.label}</label>
                  <Control field={field} value={values[field.key]} onChange={(value) => onChange(field.key, value)} />
                </div>
              ))}
            </div>
            {wide.map((field) =>
              field.kind === "multi_select" ? (
                <CheckGroup
                  key={field.key}
                  legend={field.label}
                  options={field.options}
                  picked={asList(values[field.key])}
                  onToggle={(option) => {
                    const picked = asList(values[field.key]);
                    onChange(field.key, picked.includes(option) ? picked.filter((item) => item !== option) : [...picked, option]);
                  }}
                />
              ) : (
                <div className="field" key={field.key}>
                  <label htmlFor={`detail-${field.key}`}>{field.label}</label>
                  <textarea id={`detail-${field.key}`} rows={3} value={asText(values[field.key])} onChange={(event) => onChange(field.key, event.target.value)} />
                </div>
              ),
            )}
          </section>
        );
      })}
      <p className="muted">Attio sets values here but cannot empty one. To clear a field, do it in Attio.</p>
    </>
  );
}

function Control({ field, value, onChange }: { field: FieldDef; value: DetailValue | undefined; onChange: (value: DetailValue | undefined) => void }) {
  const id = `detail-${field.key}`;
  switch (field.kind) {
    case "select":
      return (
        <select id={id} value={asText(value)} onChange={(event) => onChange(event.target.value || undefined)}>
          <option value="">Not set</option>
          {field.options.map((option) => <option key={option}>{option}</option>)}
        </select>
      );
    case "bool":
      return (
        <select id={id} value={value === true ? "yes" : value === false ? "no" : ""} onChange={(event) => onChange(event.target.value === "" ? undefined : event.target.value === "yes")}>
          <option value="">Not set</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      );
    case "currency":
      return <AmountInput id={id} value={asNumber(value)} onChange={onChange} />;
    case "number":
    case "percent":
      return (
        <input
          id={id}
          type="number"
          inputMode="decimal"
          min={0}
          max={field.kind === "percent" ? 100 : undefined}
          value={asNumber(value) ?? ""}
          onChange={(event) => onChange(event.target.value === "" ? undefined : Number(event.target.value))}
        />
      );
    case "date":
      return <input id={id} type="date" value={asText(value)} onChange={(event) => onChange(event.target.value || undefined)} />;
    default:
      return <input id={id} value={asText(value)} onChange={(event) => onChange(event.target.value || undefined)} />;
  }
}
