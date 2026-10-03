import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { invoke } from '@tauri-apps/api/core';
import Analytics from '@/lib/analytics';
import { useSidebar, type CurrentMeeting } from '@/components/Sidebar/SidebarProvider';

// Shared by the sidebar's per-meeting delete and the folder page's
// multi-select delete, so there is exactly one place that calls
// `api_delete_meeting`, updates the `meetings` list, and reports the
// result -- rather than two copies drifting apart.
export function useDeleteMeetings() {
  const { setMeetings, currentMeeting, setCurrentMeeting } = useSidebar();
  const router = useRouter();

  const deleteMeetings = useCallback(
    async (meetingIds: string[], deleteRemote: boolean) => {
      const deleted: string[] = [];
      const failed: string[] = [];
      const errors: string[] = [];

      // Sequential, not Promise.all -- a bulk delete can hit the same
      // server-side rate limit/connection the app also uses for push, and
      // a partial failure needs to leave the still-undeleted meetings alone
      // rather than racing them all at once.
      for (const meetingId of meetingIds) {
        try {
          await invoke('api_delete_meeting', { meetingId, deleteRemote });
          deleted.push(meetingId);
          Analytics.trackMeetingDeleted(meetingId);
        } catch (error) {
          console.error(`Failed to delete meeting ${meetingId}:`, error);
          failed.push(meetingId);
          errors.push(error instanceof Error ? error.message : String(error));
        }
      }

      if (deleted.length > 0) {
        const deletedSet = new Set(deleted);
        // Functional update: a refresh or new recording may have landed during the loop.
        setMeetings((current) => current.filter((m: CurrentMeeting) => !deletedSet.has(m.id)));
        if (currentMeeting?.id && deletedSet.has(currentMeeting.id)) {
          setCurrentMeeting({ id: 'intro-call', title: '+ New Call' });
          router.push('/');
        }
      }

      if (failed.length === 0) {
        toast.success(
          deleted.length === 1 ? "Meeting deleted successfully" : `${deleted.length} meetings deleted successfully`,
          { description: "All associated data has been removed" }
        );
      } else if (deleted.length === 0) {
        toast.error("Failed to delete meeting" + (meetingIds.length > 1 ? "s" : ""), {
          description: errors[0] ?? "See the console for details."
        });
      } else {
        toast.warning(`Deleted ${deleted.length} of ${meetingIds.length} meetings`, {
          description: `${failed.length} failed: ${errors[0] ?? 'see the console for details.'}`
        });
      }

      return { deleted, failed };
    },
    [setMeetings, currentMeeting, setCurrentMeeting, router]
  );

  return { deleteMeetings };
}
