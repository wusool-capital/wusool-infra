import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke as invokeTauri } from '@tauri-apps/api/core';

export interface CompanyCandidate {
  label: string;
  value: string;
}

interface CompanySearchResponse {
  candidates: CompanyCandidate[];
  org_names: Record<string, string>;
}

const DEBOUNCE_MS = 300;

/**
 * Debounced buyer/seller company search against the Scribe backend --
 * mirrors the candidates the Slack --buyer/--seller confirmation modal
 * offers (Wusool organizations, falling back to scribe's own companies).
 * `orgNames` accumulates {attio_id: name} across searches so it can be
 * sent back at push time without a second lookup.
 */
export function useCompanySearch() {
  const [candidates, setCandidates] = useState<CompanyCandidate[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const orgNamesRef = useRef<Record<string, string>>({});
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const latestQueryRef = useRef('');

  const search = useCallback((query: string) => {
    latestQueryRef.current = query;
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim()) {
      setCandidates([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const response = await invokeTauri('search_companies', { query }) as CompanySearchResponse;
        if (latestQueryRef.current === query) {
          setCandidates(response.candidates);
          orgNamesRef.current = { ...orgNamesRef.current, ...response.org_names };
        }
      } catch (err) {
        console.error('Company search failed:', err);
        if (latestQueryRef.current === query) setCandidates([]);
      } finally {
        if (latestQueryRef.current === query) setIsSearching(false);
      }
    }, DEBOUNCE_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const clearCandidates = useCallback(() => setCandidates([]), []);

  return { candidates, isSearching, search, clearCandidates, orgNames: orgNamesRef.current };
}
