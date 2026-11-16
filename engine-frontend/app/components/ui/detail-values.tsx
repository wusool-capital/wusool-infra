import { useEffect, useState, type ReactNode } from "react";
import type { Detail, DetailValue, FieldDef } from "../../demo/types";
import { formatDate, formatMoney } from "../../lib/format";
import { LinkText } from "./link-text";
import { LabelItem } from "./record-parts";

type Props = {
  fields: FieldDef[];
  /** "Buyer" or "Seller": names the group of fields on the role itself. */
  roleName: string;
  /** Changes with each record, so the values reload. */
  recordId: string;
  load: () => Promise<Detail[]>;
};

const GROUPS = [
  { group: "role", heading: (roleName: string) => `${roleName} details` },
  { group: "company", heading: () => "Company details" },
] as const;

const isEmpty = (value: DetailValue | undefined) => value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);

function show(field: FieldDef, value: DetailValue): ReactNode {
  if (Array.isArray(value)) return value.join(", ");
  switch (field.kind) {
    case "currency":
      return typeof value === "number" ? formatMoney(value) : String(value);
    case "percent":
      return `${value}%`;
    case "date":
      return typeof value === "string" ? formatDate(value) : String(value);
    case "bool":
      return value ? "Yes" : "No";
    case "text":
      return <LinkText text={String(value)} />;
    default:
      return String(value);
  }
}

/** The extra Slack fields of a record, read only. A field with no value is left out. */
export function DetailValues({ fields, roleName, recordId, load }: Props) {
  const [values, setValues] = useState<Record<string, DetailValue> | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (fields.length === 0) return;
    let current = true;
    setValues(null);
    setFailed(false);
    load()
      .then((list) => current && setValues(Object.fromEntries(list.map((detail) => [detail.key, detail.value]))))
      .catch(() => current && setFailed(true));
    return () => {
      current = false;
    };
    // `load` is a new function every render; the record id says when to reload.
  }, [recordId]);

  if (failed) return <p className="muted">Could not load the other fields.</p>;
  if (!values) return null;

  return (
    <>
      {GROUPS.map(({ group, heading }) => {
        const filled = fields.filter((field) => field.group === group && !isEmpty(values[field.key]));
        if (filled.length === 0) return null;
        const long = filled.filter((field) => field.kind === "multiline");
        const short = filled.filter((field) => field.kind !== "multiline");
        return (
          <section key={group} className="drawer__section">
            <h3 className="panel-heading">{heading(roleName)}</h3>
            {short.length > 0 && (
              <dl className="label-grid label-grid--two">
                {short.map((field) => (
                  <LabelItem key={field.key} label={field.label}>{show(field, values[field.key]!)}</LabelItem>
                ))}
              </dl>
            )}
            {long.map((field) => (
              <div key={field.key} className="detail-long">
                <h4>{field.label}</h4>
                <p>{show(field, values[field.key]!)}</p>
              </div>
            ))}
          </section>
        );
      })}
    </>
  );
}
