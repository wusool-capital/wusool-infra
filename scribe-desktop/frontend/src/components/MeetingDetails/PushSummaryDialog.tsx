"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Send, RefreshCw, CheckCircle2 } from 'lucide-react';
import { usePush, CompanyRole } from '@/hooks/meeting-details/usePush';
import { useSidebar } from '@/components/Sidebar/SidebarProvider';
import { CompanyAutocomplete, CompanySelection } from './CompanyAutocomplete';
import { SummaryView } from './SummaryView';
import Analytics from '@/lib/analytics';

const EMPTY_SELECTION: CompanySelection = { query: '', selection: null };

const ROLE_OPTIONS: { value: CompanyRole; label: string }[] = [
  { value: 'general', label: 'General' },
  { value: 'buyer', label: 'Buyer' },
  { value: 'seller', label: 'Seller' },
  { value: 'investor', label: 'Investor' },
  { value: 'internal', label: 'Internal' },
];

// Buyer/Seller/Investor are all "there's an external counterparty"
// roles -- a company name is the whole point of tagging one, so it's
// required. General/Internal have no required counterparty (per
// CompanyRole's backend docstring), so the company field stays optional
// for those two.
const ROLES_REQUIRING_COMPANY: CompanyRole[] = ['buyer', 'seller', 'investor'];

interface PushSummaryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  meetingId: string;
  initialTag?: string | null;
}

/**
 * The meeting-end workflow, in a dedicated popup: tag the meeting with a
 * role (general/buyer/seller/investor/internal) and optional company, push
 * the transcript to Scribe for server-side summarization, and show the
 * summary once Scribe returns it.
 */
export function PushSummaryDialog({ open, onOpenChange, meetingId, initialTag }: PushSummaryDialogProps) {
  const [company, setCompany] = useState<CompanySelection>(EMPTY_SELECTION);
  const [role, setRole] = useState<CompanyRole>('general');
  const [orgNames, setOrgNames] = useState<Record<string, string>>({});
  const { pushState, remoteSummary, error, saveTag, push, checkStatus } = usePush(meetingId);
  const { refetchMeetings } = useSidebar();

  const disabled = pushState === 'pushing' || pushState === 'pushed';
  const companyRequired = ROLES_REQUIRING_COMPANY.includes(role);
  const companyMissing = companyRequired && !company.query.trim();

  const handlePush = async () => {
    if (companyMissing) return;

    // Files the meeting into a sidebar folder (see SidebarProvider.baseItems)
    // named "<Company> – <Role>" so a Buyer meeting and a Seller meeting for
    // the same company land in separate, clearly-labeled folders instead of
    // merging silently. Internal/General meetings usually have no company
    // at all -- those fall back to a role-only tag ("Internal"/"General"),
    // so every untagged-company internal meeting lands in one shared folder
    // instead of each getting no folder at all.
    const companyText = company.query.trim();
    const roleLabel = ROLE_OPTIONS.find((option) => option.value === role)?.label ?? '';
    const tag = companyText ? `${companyText} – ${roleLabel}` : roleLabel;
    await saveTag(tag);
    await refetchMeetings();
    Analytics.trackButtonClick('push_meeting', 'meeting_details');
    await push(company, role, orgNames);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Summarize meeting</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex items-end gap-2">
            <CompanyAutocomplete
              label="Company"
              placeholder="Search or type a company name"
              value={company}
              onChange={(next, names) => {
                setCompany(next);
                setOrgNames((prev) => ({ ...prev, ...names }));
              }}
              disabled={disabled}
            />
            <Button
              onClick={handlePush}
              disabled={disabled || companyMissing}
              title={
                companyMissing
                  ? `Enter a company name for a ${role} meeting before pushing`
                  : 'Push transcript to Scribe for summarization'
              }
            >
              {pushState === 'pushed' ? <CheckCircle2 /> : <Send />}
              <span className="hidden lg:inline">
                {pushState === 'pushing' ? 'Pushing...' : pushState === 'pushed' ? 'Pushed' : 'Push'}
              </span>
            </Button>
          </div>

          <div className="flex items-center gap-1 bg-card border border-border rounded-md p-1 w-fit">
            {ROLE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setRole(option.value)}
                disabled={disabled}
                className={`px-3 py-1 text-sm rounded transition-colors ${
                  role === option.value
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:bg-accent'
                } disabled:opacity-50`}
              >
                {option.label}
              </button>
            ))}
          </div>

          {companyMissing && (
            <p className="text-xs text-destructive -mt-2">
              Enter a company name for a {role} meeting before pushing.
            </p>
          )}

          {pushState === 'pushed' && !remoteSummary && (
            <div className="flex items-center justify-between text-sm text-muted-foreground ">
              <span>Waiting for summary from Scribe...</span>
              <Button
                size="sm"
                variant="outline"
                onClick={async () => {
                  await checkStatus();
                  // Picks up the AI-generated title checkStatus may have
                  // just saved, so the sidebar's placeholder timestamp
                  // title updates without needing a manual refresh.
                  await refetchMeetings();
                }}
              >
                <RefreshCw size={14} />
                <span className="hidden lg:inline">Check</span>
              </Button>
            </div>
          )}

          {remoteSummary && (
            <div className="bg-card border border-border rounded-md p-4 max-h-[50vh] overflow-y-auto">
              <SummaryView summary={remoteSummary} />
            </div>
          )}

          {pushState === 'error' && error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
