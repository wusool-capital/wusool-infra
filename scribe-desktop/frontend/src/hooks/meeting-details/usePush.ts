import { useCallback, useState } from 'react';
import { invoke as invokeTauri } from '@tauri-apps/api/core';
import { toast } from 'sonner';
import { CompanySelection, CREATE_NEW_VALUE } from '@/components/MeetingDetails/CompanyAutocomplete';

export type PushState = 'idle' | 'pushing' | 'pushed' | 'error';
export type CompanyRole = 'general' | 'buyer' | 'seller' | 'investor' | 'internal';

// A typed-but-unconfirmed company name still resolves as "create new" on
// push, rather than silently dropping the tag -- matches the desktop
// app's more forgiving flow (no forced modal) while still going through
// the same resolution path as an explicit confirmation.
function resolvedSelection(company: CompanySelection): string | null {
  if (company.selection !== null) return company.selection;
  return company.query.trim() ? CREATE_NEW_VALUE : null;
}

interface DesktopMeetingSubmitResponse {
  meeting_id: string;
  status: string;
  already_existed: boolean;
}

interface DesktopMeetingStatusResponse {
  meeting_id: string;
  status: string;
  summary: Record<string, unknown> | null;
}

/**
 * Push flow: sends the finished, edited transcript to the Scribe EC2
 * backend once the user tags the meeting and clicks Push. Push is
 * one-shot per meeting -- a second push for the same meeting_id is
 * rejected by the backend (409), which surfaces as an error here
 * rather than silently doing nothing, since re-editing after a push
 * would otherwise look like it worked but never reach the backend.
 */
export function usePush(meetingId: string) {
  const [pushState, setPushState] = useState<PushState>('idle');
  const [remoteMeetingId, setRemoteMeetingId] = useState<string | null>(null);
  const [remoteSummary, setRemoteSummary] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const saveTag = useCallback(async (tag: string) => {
    try {
      await invokeTauri('update_meeting_tag', { meetingId, tag });
      return true;
    } catch (err) {
      console.error('Failed to save meeting tag:', err);
      toast.error('Failed to save tag');
      return false;
    }
  }, [meetingId]);

  const push = useCallback(async (
    company: CompanySelection,
    role: CompanyRole,
    orgNames: Record<string, string>,
  ) => {
    setPushState('pushing');
    setError(null);
    try {
      const companyQuery = company.query.trim() || null;
      const companySelection = resolvedSelection(company);

      const response = await invokeTauri('push_meeting', {
        meetingId,
        slackChannelId: null,
        buyerQuery: role === 'buyer' ? companyQuery : null,
        buyerSelection: role === 'buyer' ? companySelection : null,
        sellerQuery: role === 'seller' ? companyQuery : null,
        sellerSelection: role === 'seller' ? companySelection : null,
        investorQuery: role === 'investor' ? companyQuery : null,
        investorSelection: role === 'investor' ? companySelection : null,
        internalQuery: role === 'internal' ? companyQuery : null,
        internalSelection: role === 'internal' ? companySelection : null,
        generalQuery: role === 'general' ? companyQuery : null,
        generalSelection: role === 'general' ? companySelection : null,
        orgNames,
      }) as DesktopMeetingSubmitResponse;

      setRemoteMeetingId(response.meeting_id);
      setPushState('pushed');
      toast.success('Pushed to Scribe -- summary will appear here once ready.');
    } catch (err) {
      const message = typeof err === 'string' ? err : 'Failed to push meeting';
      console.error('Failed to push meeting:', err);
      setError(message);
      setPushState('error');
      toast.error(message);
    }
  }, [meetingId]);

  const checkStatus = useCallback(async () => {
    if (!remoteMeetingId) return;
    try {
      // meetingId (local) lets the backend command file the summary into
      // this meeting's existing recording folder alongside its audio and
      // transcripts.json once it's found -- get_push_status also applies
      // the AI-generated title itself (over a still-placeholder title)
      // via the same helper sync_pushed_meetings uses, so there's exactly
      // one title-normalizer instead of a second copy here.
      const response = await invokeTauri('get_push_status', {
        meetingId,
        remoteMeetingId,
      }) as DesktopMeetingStatusResponse;
      if (response.summary) {
        setRemoteSummary(response.summary);
        toast.success('Summary saved alongside the recording and transcript');
      }
    } catch (err) {
      console.error('Failed to check push status:', err);
      toast.error('Failed to check push status');
    }
  }, [meetingId, remoteMeetingId]);

  return {
    pushState,
    remoteMeetingId,
    remoteSummary,
    error,
    saveTag,
    push,
    checkStatus,
  };
}
