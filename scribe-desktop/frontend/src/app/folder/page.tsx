"use client";

import { Suspense, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, File, Folder, LoaderIcon, SearchIcon, X } from 'lucide-react';
import { useSidebar, slugifyTag } from '@/components/Sidebar/SidebarProvider';
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '@/components/ui/input-group';

// Mirrors Sidebar/index.tsx's formatDuration/formatMeetingDate (not
// shared: these are a few lines each, not worth extracting).
function formatDuration(seconds?: number | null): string | null {
  if (!seconds || seconds <= 0) return null;
  const totalMinutes = Math.ceil(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

function formatMeetingDate(createdAt?: string | null): string | null {
  if (!createdAt) return null;
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return null;
  const includeYear = date.getFullYear() !== new Date().getFullYear();
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: includeYear ? 'numeric' : undefined,
  });
}

function FolderContent() {
  const searchParams = useSearchParams();
  const tagSlug = searchParams.get('tag') ?? '';
  const folderName = searchParams.get('name') ?? 'Folder';
  const router = useRouter();
  const { meetings, setCurrentMeeting } = useSidebar();
  const [searchQuery, setSearchQuery] = useState('');

  // Matches SidebarProvider.baseItems' own grouping key exactly, so this
  // list is always identical to what the sidebar folder represents.
  const folderMeetings = useMemo(
    () => meetings.filter((m) => m.pushTag && slugifyTag(m.pushTag) === tagSlug),
    [meetings, tagSlug]
  );

  // Search within this folder only -- a plain client-side title filter,
  // not the transcript-content search the main sidebar does, since a
  // folder's meeting count is small enough that title matching is what
  // actually helps someone re-find a specific meeting here.
  const visibleMeetings = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return folderMeetings;
    return folderMeetings.filter((m) => m.title.toLowerCase().includes(query));
  }, [folderMeetings, searchQuery]);

  return (
    <div className="h-screen bg-muted flex flex-col">
      <div className="sticky top-0 z-10 bg-muted border-b border-border ">
        <div className="px-8 py-6">
          <div className="flex items-center gap-4 mb-2">
            <button
              onClick={() => router.back()}
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span>Back</span>
            </button>
          </div>
          <div className="flex items-center gap-3">
            <Folder className="w-6 h-6 text-muted-foreground " />
            <h1 className="text-2xl font-bold text-foreground ">{folderName}</h1>
            <span className="text-sm text-muted-foreground ">
              {folderMeetings.length} meeting{folderMeetings.length === 1 ? '' : 's'}
            </span>
          </div>

          <div className="mt-4">
            <InputGroup>
              <InputGroupInput
                placeholder={`Search in ${folderName}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <InputGroupAddon>
                <SearchIcon />
              </InputGroupAddon>
              {searchQuery && (
                <InputGroupAddon align="inline-end">
                  <InputGroupButton onClick={() => setSearchQuery('')}>
                    <X />
                  </InputGroupButton>
                </InputGroupAddon>
              )}
            </InputGroup>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="p-8 pt-4">
          {folderMeetings.length === 0 ? (
            <p className="text-sm text-muted-foreground ">No meetings in this folder.</p>
          ) : visibleMeetings.length === 0 ? (
            <p className="text-sm text-muted-foreground ">No meetings match &ldquo;{searchQuery}&rdquo;.</p>
          ) : (
            <div className="space-y-2">
              {visibleMeetings.map((meeting) => (
                <button
                  key={meeting.id}
                  onClick={() => {
                    setCurrentMeeting({ id: meeting.id, title: meeting.title });
                    router.push(`/meeting-details?id=${meeting.id}`);
                  }}
                  className="w-full flex items-center gap-3 p-3 bg-card border border-border rounded-lg hover:bg-accent/60 hover:border-foreground/30 transition-colors text-left"
                >
                  <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-muted ">
                    <File className="w-4 h-4 text-muted-foreground " />
                  </div>
                  <span className="text-sm font-medium text-foreground truncate min-w-0" title={meeting.title}>
                    {meeting.title}
                  </span>
                  {(formatMeetingDate(meeting.createdAt) || formatDuration(meeting.durationSeconds)) && (
                    <span className="flex-shrink-0 ml-auto text-[11px] text-muted-foreground whitespace-nowrap">
                      {[formatMeetingDate(meeting.createdAt), formatDuration(meeting.durationSeconds)]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function FolderPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen">
        <LoaderIcon className="animate-spin size-6" />
      </div>
    }>
      <FolderContent />
    </Suspense>
  );
}
