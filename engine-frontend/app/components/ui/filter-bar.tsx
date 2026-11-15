import { CaretDown } from "@phosphor-icons/react";
import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { formatMoney } from "../../lib/format";
import { optionLabel, optionValue, readList, readRange, writeList, writeRange, type FilterDef, type ListFilter, type Range, type RangeFilter } from "../../lib/filters";
import { RangeSlider } from "./range-slider";
import { useDismiss } from "./use-dismiss";

type Props = {
  /** Shown before the filters, such as a view switch or a search box. */
  before?: ReactNode;
  filters: FilterDef[];
  /** Shown at the end of the row, such as the Search button or a primary action. */
  children?: ReactNode;
  /** Other URL keys that Clear filters also removes, such as a search already run and its sentence. */
  alsoClear?: string[];
  /** Rows shown and rows in total: the count appears only while a filter hides some. */
  shown?: number;
  total?: number;
};

/**
 * One button per filter. Its panel holds a draft; nothing changes until Apply, so each
 * Apply is one query once the lists come from the Toolkit (Jules, 7 Nov 2026).
 */
export function FilterBar({ before, filters, children, shown, total, alsoClear = [] }: Props) {
  const [params, setParams] = useSearchParams();
  // A filter with a fallback keeps an empty value in the URL, so "all" is not read back as the fallback.
  const keepsEmpty = (filter: FilterDef) => filter.kind === "list" && filter.fallback !== undefined;
  const apply = (filter: FilterDef, value: string) =>
    setParams(
      (next) => {
        if (value || keepsEmpty(filter)) next.set(filter.key, value);
        else next.delete(filter.key);
        return next;
      },
      { preventScrollReset: true },
    );
  const anyActive = filters.some((filter) => narrows(filter, params)) || alsoClear.some((key) => params.has(key));

  return (
    <div className="toolbar">
      {before}
      {filters.map((filter) => (
        <FilterButton key={filter.key} filter={filter} params={params} onApply={(value) => apply(filter, value)} />
      ))}
      {anyActive && (
        <button
          type="button"
          className="button button--quiet"
          onClick={() =>
            setParams(
              (next) => {
                for (const filter of filters) {
                  if (keepsEmpty(filter)) next.set(filter.key, "");
                  else next.delete(filter.key);
                }
                for (const key of alsoClear) next.delete(key);
                return next;
              },
              { preventScrollReset: true },
            )
          }
        >
          {shown !== undefined && total !== undefined && shown !== total ? `Clear filters (${shown} of ${total})` : "Clear filters"}
        </button>
      )}
      {children}
    </div>
  );
}

type ButtonProps = { filter: FilterDef; params: URLSearchParams; onApply: (value: string) => void };

function FilterButton({ filter, params, onApply }: ButtonProps) {
  const [open, setOpen] = useState(false);
  const dismiss = useDismiss<HTMLDivElement>(open, () => setOpen(false));
  const summary = summaryOf(filter, params);

  return (
    <div
      className="filter"
      ref={dismiss.ref}
      onBlur={dismiss.onBlur}
      onKeyDown={(event) => {
        if (event.key === "Escape") setOpen(false);
      }}
    >
      <button type="button" className="filter__button" data-active={narrows(filter, params) ? "yes" : "no"} aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="filter__label">{summary ? `${filter.label}: ${summary}` : filter.label}</span>
        <CaretDown size={14} aria-hidden="true" />
      </button>
      {open &&
        (filter.kind === "list" ? (
          <ListPanel filter={filter} initial={readList(params, filter.key, filter.fallback)} onApply={(values) => (onApply(writeList(values)), setOpen(false))} />
        ) : (
          <RangePanel filter={filter} initial={readRange(params, filter.key)} onApply={(range) => (onApply(writeRange(range)), setOpen(false))} />
        ))}
    </div>
  );
}

/** True when the filter hides some rows. */
function narrows(filter: FilterDef, params: URLSearchParams) {
  if (filter.kind === "range") return rangeSummary(readRange(params, filter.key)) !== "";
  return readList(params, filter.key, filter.fallback).length > 0;
}

function summaryOf(filter: FilterDef, params: URLSearchParams) {
  if (filter.kind === "range") return rangeSummary(readRange(params, filter.key));
  const labels = readList(params, filter.key, filter.fallback).map((value) => optionLabel(filter.options.find((option) => optionValue(option) === value) ?? value));
  // A filter with a default (Owner: me) says "All" when cleared, so the change is visible.
  if (labels.length === 0) return filter.fallback ? "All" : "";
  return labels.length === 1 ? labels[0] : `${labels[0]} +${labels.length - 1}`;
}

function rangeSummary({ min, max }: Range) {
  if (min !== undefined && max !== undefined) return `${stopLabel(min)} to ${stopLabel(max)}`;
  if (min !== undefined) return `${stopLabel(min)} and over`;
  if (max !== undefined) return `Up to ${stopLabel(max)}`;
  return "";
}

function PanelFooter({ onClear, onApply, disabled = false }: { onClear: () => void; onApply: () => void; disabled?: boolean }) {
  return (
    <div className="filter__footer">
      <button type="button" className="button button--small button--quiet" onClick={onClear}>
        Clear
      </button>
      <button type="button" className="button button--small" disabled={disabled} onClick={onApply}>
        Apply
      </button>
    </div>
  );
}

// Type to narrow the list, tick one or more.
function ListPanel({ filter, initial, onApply }: { filter: ListFilter; initial: string[]; onApply: (values: string[]) => void }) {
  const [picked, setPicked] = useState(initial);
  const [query, setQuery] = useState("");
  const shown = filter.options.filter((option) => optionLabel(option).toLowerCase().includes(query.trim().toLowerCase()));
  const toggle = (value: string) => setPicked((now) => (now.includes(value) ? now.filter((item) => item !== value) : [...now, value]));

  return (
    <div className="filter__panel" role="dialog" aria-label={filter.label}>
      {filter.options.length > 6 && (
        <input
          className="filter__search"
          type="search"
          aria-label={`Search ${filter.label.toLowerCase()}`}
          placeholder={`Type a ${filter.label.toLowerCase()}`}
          value={query}
          autoFocus
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && onApply(picked)}
        />
      )}
      <ul className="filter__options">
        {!query.trim() && (
          <li>
            <label className="filter__option filter__option--all">
              <input type="checkbox" checked={picked.length === 0} onChange={() => setPicked([])} />
              All
            </label>
          </li>
        )}
        {shown.map((option) => (
          <li key={optionValue(option)}>
            <label className="filter__option">
              <input type="checkbox" checked={picked.includes(optionValue(option))} onChange={() => toggle(optionValue(option))} />
              {optionLabel(option)}
            </label>
          </li>
        ))}
        {shown.length === 0 && <li className="muted filter__none">No match</li>}
      </ul>
      <PanelFooter onClear={() => setPicked([])} onApply={() => onApply(picked)} />
    </div>
  );
}

// Positions the thumbs snap to, in USD. The first reads "Any" and the last "No limit", so an open end
// needs no empty box, and a value is always one the screen names ($200K, never "0.2").
const STOPS = [
  0, 100_000, 200_000, 300_000, 400_000, 500_000, 750_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000,
  7_500_000, 10_000_000, 15_000_000, 20_000_000, 25_000_000, 30_000_000, 40_000_000, 50_000_000, 75_000_000, 100_000_000,
  150_000_000, 250_000_000, 500_000_000, 1_000_000_000,
];
const LAST = STOPS.length - 1;

const stopLabel = (usd: number) => (usd >= 1_000_000_000 ? "$1B" : formatMoney(usd));

/** The stop closest to a value from the URL; an open end sits on its end stop. */
function stopFor(usd: number | undefined, openEnd: number) {
  if (usd === undefined) return openEnd;
  return STOPS.reduce((best, stop, index) => (Math.abs(stop - usd) < Math.abs(STOPS[best] - usd) ? index : best), 0);
}

function RangePanel({ filter, initial, onApply }: { filter: RangeFilter; initial: Range; onApply: (range: Range) => void }) {
  const [thumbs, setThumbs] = useState<[number, number]>([stopFor(initial.min, 0), stopFor(initial.max, LAST)]);
  const range: Range = { min: thumbs[0] === 0 ? undefined : STOPS[thumbs[0]], max: thumbs[1] === LAST ? undefined : STOPS[thumbs[1]] };

  return (
    <div className="filter__panel" role="dialog" aria-label={filter.label}>
      <p className="filter__readout" aria-live="polite">{rangeSummary(range) || "Any"}</p>
      <RangeSlider label={filter.label} stops={STOPS} value={thumbs} onChange={setThumbs} format={(usd) => (usd === 0 ? "Any" : stopLabel(usd))} />
      <div className="filter__ends" aria-hidden="true">
        <span>Any</span>
        <span>{stopLabel(STOPS[LAST])}+</span>
      </div>
      <p className="muted filter__note">Rows with no value here are hidden while a range is set.</p>
      <PanelFooter onClear={() => setThumbs([0, LAST])} onApply={() => onApply(range)} />
    </div>
  );
}
