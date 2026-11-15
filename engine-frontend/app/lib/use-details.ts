import { useEffect, useState } from "react";
import type { Detail, DetailValue, FieldDef } from "../demo/types";

type Values = Record<string, DetailValue | undefined>;

const isEmpty = (value: DetailValue | undefined) => value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
const same = (a: DetailValue | undefined, b: DetailValue | undefined) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/**
 * The values of the extra Slack fields. An existing record loads its current values; a new one
 * starts empty. Attio's edit only sets values, so a cleared field is reported, not sent.
 */
export function useDetails(fields: FieldDef[], load: (() => Promise<Detail[]>) | null) {
  const [loaded, setLoaded] = useState<Values>({});
  const [values, setValues] = useState<Values>({});
  const [status, setStatus] = useState<"loading" | "ready" | "failed">(load && fields.length ? "loading" : "ready");

  useEffect(() => {
    if (!load || fields.length === 0) return;
    let current = true;
    load()
      .then((list) => {
        if (!current) return;
        const map = Object.fromEntries(list.map((detail) => [detail.key, detail.value]));
        setLoaded(map);
        setValues(map);
        setStatus("ready");
      })
      .catch(() => current && setStatus("failed"));
    return () => {
      current = false;
    };
    // Loaded once per opened record.
  }, []);

  const changed = fields.filter((field) => !same(values[field.key], loaded[field.key]));
  return {
    values,
    status,
    set: (key: string, value: DetailValue | undefined) => setValues((current) => ({ ...current, [key]: value })),
    /** What to send: changed fields that hold a value. */
    changes: changed.filter((field) => !isEmpty(values[field.key])).map((field): Detail => ({ key: field.key, value: values[field.key] ?? null })),
    dirty: changed.length > 0,
    /** Fields that had a value and were emptied. */
    cleared: changed.filter((field) => isEmpty(values[field.key]) && !isEmpty(loaded[field.key])).map((field) => field.label),
  };
}
