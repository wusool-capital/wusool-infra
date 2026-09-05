"use client";

import { useEffect, useRef, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Check, Loader2, Plus } from 'lucide-react';
import { useCompanySearch, CompanyCandidate } from '@/hooks/meeting-details/useCompanySearch';

export const CREATE_NEW_VALUE = '__create_new__';

export interface CompanySelection {
  query: string;
  /** Confirmed candidate value ("attio:<id>" | company UUID | CREATE_NEW_VALUE), or null if unconfirmed. */
  selection: string | null;
}

interface CompanyAutocompleteProps {
  label: string;
  placeholder: string;
  value: CompanySelection;
  onChange: (value: CompanySelection, orgNames: Record<string, string>) => void;
  disabled?: boolean;
}

/**
 * Buyer/seller company picker — types a name, fuzzy-matches against
 * Wusool organizations / scribe's own companies (same source and value
 * encoding as the Slack --buyer/--seller confirmation modal), and
 * confirms a candidate or creates a new company. Confirmation is always
 * required before push, matching the Slack flow's stance that even a
 * high-confidence match still needs an explicit pick.
 */
export function CompanyAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  disabled,
}: CompanyAutocompleteProps) {
  const { candidates, isSearching, search, clearCandidates, orgNames } = useCompanySearch();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleQueryChange = (query: string) => {
    onChange({ query, selection: null }, orgNames);
    search(query);
    setIsOpen(true);
  };

  const handleSelect = (candidateValue: string, candidateLabel: string) => {
    onChange({ query: candidateLabel, selection: candidateValue }, orgNames);
    clearCandidates();
    setIsOpen(false);
  };

  const confirmed = value.selection !== null;

  return (
    <div ref={containerRef} className="relative flex-1">
      <label className="block text-xs font-medium text-muted-foreground mb-1">{label}</label>
      <div className="relative">
        <Input
          placeholder={placeholder}
          value={value.query}
          onChange={(e) => handleQueryChange(e.target.value)}
          onFocus={() => value.query.trim() && setIsOpen(true)}
          disabled={disabled}
          className={confirmed ? 'pr-7' : ''}
        />
        {confirmed && (
          <Check size={16} className="absolute right-2 top-1/2 -translate-y-1/2 text-success" />
        )}
      </div>

      {isOpen && value.query.trim() && (
        <div className="absolute z-10 mt-1 w-full bg-card border border-border rounded-md shadow-lg max-h-56 overflow-y-auto">
          {isSearching && (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground ">
              <Loader2 size={14} className="animate-spin" /> Searching...
            </div>
          )}
          {!isSearching &&
            candidates.map((candidate: CompanyCandidate) => (
              <button
                key={candidate.value}
                type="button"
                onClick={() => handleSelect(candidate.value, candidate.label)}
                className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-accent/60 flex items-center justify-between"
              >
                <span>{candidate.label}</span>
                {candidate.value.startsWith('attio:') && (
                  <span className="text-xs text-primary flex-shrink-0 ml-2">Attio</span>
                )}
              </button>
            ))}
          <button
            type="button"
            onClick={() => handleSelect(CREATE_NEW_VALUE, value.query)}
            className="w-full text-left px-3 py-2 text-sm hover:bg-accent/60 flex items-center gap-2 border-t border-border text-foreground/90 "
          >
            <Plus size={14} />
            Create new: &ldquo;{value.query}&rdquo;
          </button>
        </div>
      )}
    </div>
  );
}
