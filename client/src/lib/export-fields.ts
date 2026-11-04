import { useSyncExternalStore } from "react";
import { z } from "zod";

import {
  exportMatchRunFieldsEnum,
  type ExportMatchRunFieldsEnumKey,
} from "@/gen/types/ExportMatchRun";

export type ExportField = ExportMatchRunFieldsEnumKey;

export const EXPORT_FIELDS: readonly { id: ExportField; label: string }[] = [
  { id: "rank", label: "Rank" },
  { id: "seller", label: "Seller" },
  { id: "origin", label: "Source (CRM or discovered)" },
  { id: "match_score", label: "Match score" },
  { id: "status", label: "Decision" },
  { id: "why_it_matches", label: "Why it matches" },
  { id: "recommended_pitch", label: "Recommended pitch" },
  { id: "risks_and_gaps", label: "Risks and gaps" },
  { id: "why_chosen_over_alternatives", label: "Why chosen over others" },
  { id: "data_confidence", label: "Data confidence" },
  { id: "source_url", label: "Source link" },
  { id: "seller_attio_id", label: "Attio record ID" },
  { id: "research_saved", label: "Research saved" },
];

export const EXPORT_PRESETS = {
  business: {
    label: "Business",
    fields: [
      "rank",
      "seller",
      "match_score",
      "status",
      "why_it_matches",
      "recommended_pitch",
      "risks_and_gaps",
    ],
  },
  everything: {
    label: "Everything",
    fields: EXPORT_FIELDS.map((f) => f.id),
  },
} as const satisfies Record<
  string,
  { label: string; fields: readonly ExportField[] }
>;
export type ExportPreset = keyof typeof EXPORT_PRESETS;

const STORAGE_KEY = "wusool.export-fields";
const DEFAULT: readonly ExportField[] = EXPORT_PRESETS.business.fields;
const fieldsSchema = z
  .array(z.enum(exportMatchRunFieldsEnum))
  .min(1)
  .transform((fields) => orderFields(fields));

const listeners = new Set<() => void>();
let cache: { raw: string | null; fields: readonly ExportField[] } = {
  raw: null,
  fields: DEFAULT,
};

// Columns always follow the settings list order, whatever order they were ticked in.
export function orderFields(fields: readonly ExportField[]): ExportField[] {
  return EXPORT_FIELDS.map((f) => f.id).filter((id) => fields.includes(id));
}

function read(): readonly ExportField[] {
  let raw: string | null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    return cache.fields;
  }
  if (raw === cache.raw) return cache.fields;
  let fields: readonly ExportField[] = DEFAULT;
  try {
    const parsed = fieldsSchema.safeParse(JSON.parse(raw ?? "null"));
    if (parsed.success) fields = parsed.data;
  } catch {
    fields = DEFAULT;
  }
  cache = { raw, fields };
  return fields;
}

export function getExportFields(): readonly ExportField[] {
  return read();
}

export function setExportFields(fields: readonly ExportField[]): void {
  if (fields.length === 0) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(orderFields(fields)));
  } catch {
    return;
  }
  listeners.forEach((notify) => {
    notify();
  });
}

export function matchingPreset(
  fields: readonly ExportField[],
): ExportPreset | null {
  const key = orderFields(fields).join();
  for (const [id, preset] of Object.entries(EXPORT_PRESETS))
    if (orderFields(preset.fields).join() === key) return id as ExportPreset;
  return null;
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

export function useExportFields(): readonly ExportField[] {
  return useSyncExternalStore(subscribe, read, () => DEFAULT);
}
