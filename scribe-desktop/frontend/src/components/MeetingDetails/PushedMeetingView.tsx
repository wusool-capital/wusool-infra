"use client";

import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { FolderOpen, FileText, Sparkles, Mic, Copy, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Transcript, TranscriptSegmentData } from '@/types';
import { TranscriptPanel } from './TranscriptPanel';
import { SummaryView, summaryToPlainText } from './SummaryView';

interface PushedMeetingViewProps {
  meetingId: string;
  folderPath?: string | null;
  transcripts: Transcript[];
  segments?: TranscriptSegmentData[];
  hasMore?: boolean;
  isLoadingMore?: boolean;
  totalCount?: number;
  loadedCount?: number;
  onLoadMore?: () => void;
  onCopyTranscript: () => void;
  onOpenMeetingFolder: () => Promise<void>;
}

/**
 * View for a meeting that has already been pushed and summarized --
 * no editing, no Summarize button (push is one-shot). Splits Summary,
 * Transcript, and Recording into their own tabs instead of the
 * transcript-first layout used before a push.
 */
export function PushedMeetingView({
  meetingId,
  folderPath,
  transcripts,
  segments,
  hasMore,
  isLoadingMore,
  totalCount,
  loadedCount,
  onLoadMore,
  onCopyTranscript,
  onOpenMeetingFolder,
}: PushedMeetingViewProps) {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);
  const [isChecking, setIsChecking] = useState(false);

  const loadSummary = useCallback(async () => {
    try {
      const result = await invoke('get_saved_summary', { meetingId });
      setSummary((result as Record<string, unknown> | null) ?? null);
    } catch (error) {
      console.error('Failed to load saved summary:', error);
    }
  }, [meetingId]);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingSummary(true);
    loadSummary().finally(() => {
      if (!cancelled) setIsLoadingSummary(false);
    });
    return () => {
      cancelled = true;
    };
  }, [loadSummary]);

  useEffect(() => {
    // The background sync timer (lib.rs) can file this meeting's summary
    // while this view is open and showing the "No summary available
    // yet" dead end -- re-read it from disk instead of leaving the user
    // to navigate away and back.
    const unlisten = listen<number>('pushed-summaries-synced', () => {
      loadSummary();
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [loadSummary]);

  const handleCheckNow = async () => {
    setIsChecking(true);
    try {
      const result = (await invoke('sync_pushed_meetings')) as { synced: number; error?: string | null };
      await loadSummary();
      if (result.error) {
        toast.error(result.error);
      } else if (result.synced === 0) {
        toast.info('No new summary yet. Scribe may still be processing it.');
      }
    } catch (error) {
      console.error('Failed to check for summary:', error);
      toast.error('Failed to check for summary');
    } finally {
      setIsChecking(false);
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-card ">
      <Tabs defaultValue="summary" className="flex flex-col h-full">
        <div className="p-4 border-b border-border ">
          <TabsList>
            <TabsTrigger value="summary" className="gap-1.5">
              <Sparkles size={14} /> Summary
            </TabsTrigger>
            <TabsTrigger value="transcript" className="gap-1.5">
              <FileText size={14} /> Transcript
            </TabsTrigger>
            <TabsTrigger value="recording" className="gap-1.5">
              <Mic size={14} /> Recording
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="summary" className="flex-1 overflow-y-auto p-6 mt-0">
          {isLoadingSummary ? (
            <p className="text-sm text-muted-foreground ">Loading summary...</p>
          ) : summary ? (
            <div className="space-y-4">
              <div className="flex justify-end">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(summaryToPlainText(summary));
                    toast.success('Summary copied to clipboard');
                  }}
                  title="Copy Summary"
                >
                  <Copy />
                  <span className="hidden lg:inline">Copy</span>
                </Button>
              </div>
              <SummaryView summary={summary} />
            </div>
          ) : (
            <div className="flex flex-col items-start gap-3">
              <p className="text-sm text-muted-foreground ">
                No summary available yet. Scribe may still be processing it.
              </p>
              <Button size="sm" variant="outline" onClick={handleCheckNow} disabled={isChecking}>
                <RefreshCw size={14} className={isChecking ? 'animate-spin' : undefined} />
                <span>{isChecking ? 'Checking...' : 'Check now'}</span>
              </Button>
            </div>
          )}
        </TabsContent>

        <TabsContent value="transcript" className="flex-1 overflow-hidden mt-0">
          <TranscriptPanel
            transcripts={transcripts}
            onCopyTranscript={onCopyTranscript}
            onOpenMeetingFolder={onOpenMeetingFolder}
            isRecording={false}
            disableAutoScroll={true}
            usePagination={true}
            segments={segments}
            hasMore={hasMore}
            isLoadingMore={isLoadingMore}
            totalCount={totalCount}
            loadedCount={loadedCount}
            onLoadMore={onLoadMore}
            meetingId={meetingId}
            meetingFolderPath={folderPath}
            editable={false}
            showActions={false}
          />
        </TabsContent>

        <TabsContent value="recording" className="flex-1 overflow-y-auto p-6 mt-0">
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-foreground mb-1">Recording folder</h3>
              <p className="text-sm text-muted-foreground break-all font-mono text-xs">
                {folderPath || 'No recording folder for this meeting'}
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={onOpenMeetingFolder}
              disabled={!folderPath}
            >
              <FolderOpen size={16} />
              Open Recording Folder
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
