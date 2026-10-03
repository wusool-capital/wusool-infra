"use client";

import { Suspense, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { File, Folder, LoaderIcon, SearchIcon, Square, SquareCheckBig, Trash2, X } from 'lucide-react';
import { useSidebar, slugifyTag } from '@/components/Sidebar/SidebarProvider';
import { useDeleteMeetings } from '@/hooks/useDeleteMeetings';
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '@/components/ui/input-group';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ConfirmationModal } from '@/components/ConfirmationModel/confirmation-modal';

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

interface FolderViewProps {
  tagSlug: string;
  folderName: string;
}

function FolderView({ tagSlug, folderName }: FolderViewProps) {
  const router = useRouter();
  const { meetings, setCurrentMeeting } = useSidebar();
  const { deleteMeetings } = useDeleteMeetings();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteRemoteChecked, setDeleteRemoteChecked] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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

  const exitSelectionMode = () => {
    setSelectionMode(false);
    setSelectedIds(new Set());
  };

  const toggleSelected = (meetingId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(meetingId)) next.delete(meetingId);
      else next.add(meetingId);
      return next;
    });
  };

  // "Entire folder" means every meeting in it, not just the ones a search shows.
  const allSelected = selectedIds.size > 0 && selectedIds.size === folderMeetings.length;
  const allVisibleSelected =
    visibleMeetings.length > 0 && visibleMeetings.every((m) => selectedIds.has(m.id));
  const anyPushedSelected = folderMeetings.some((m) => selectedIds.has(m.id) && !!m.pushedAt);

  const handleDeleteConfirm = async () => {
    setShowDeleteConfirm(false);
    const ids = Array.from(selectedIds);
    exitSelectionMode();
    await deleteMeetings(ids, anyPushedSelected && deleteRemoteChecked);
    setDeleteRemoteChecked(false);
  };

  return (
    <div className="h-screen bg-muted flex flex-col">
      <div className="sticky top-0 z-10 bg-muted border-b border-border ">
        <div className="px-8 py-6">
          <div className="flex items-center gap-3">
            <Folder className="w-6 h-6 text-muted-foreground " />
            <h1 className="text-2xl font-bold text-foreground ">{folderName}</h1>
            <span className="text-sm text-muted-foreground ">
              {folderMeetings.length} meeting{folderMeetings.length === 1 ? '' : 's'}
            </span>
            <div className="ml-auto flex items-center gap-2">
              {selectionMode ? (
                <>
                  <span className="text-sm text-muted-foreground">
                    {selectedIds.size} selected
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setSelectedIds(allVisibleSelected ? new Set() : new Set(visibleMeetings.map((m) => m.id)))
                    }
                  >
                    {allVisibleSelected ? <Square /> : <SquareCheckBig />}
                    {allVisibleSelected ? 'Deselect all' : 'Select all'}
                  </Button>
                  <Button variant="outline" size="sm" onClick={exitSelectionMode}>
                    <X />
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={selectedIds.size === 0}
                    onClick={() => setShowDeleteConfirm(true)}
                  >
                    <Trash2 />
                    Delete{selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}
                  </Button>
                </>
              ) : (
                folderMeetings.length > 0 && (
                  <Button variant="outline" size="sm" onClick={() => setSelectionMode(true)}>
                    <SquareCheckBig />
                    Select
                  </Button>
                )
              )}
            </div>
          </div>

          <div className="mt-4">
            <InputGroup>
              <InputGroupInput
                placeholder={`Search in ${folderName}...`}
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setSelectedIds(new Set());
                }}
              />
              <InputGroupAddon>
                <SearchIcon />
              </InputGroupAddon>
              {searchQuery && (
                <InputGroupAddon align="inline-end">
                  <InputGroupButton
                    onClick={() => {
                      setSearchQuery('');
                      setSelectedIds(new Set());
                    }}
                  >
                    <X />
                  </InputGroupButton>
                </InputGroupAddon>
              )}
            </InputGroup>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
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
                    if (selectionMode) {
                      toggleSelected(meeting.id);
                      return;
                    }
                    setCurrentMeeting({ id: meeting.id, title: meeting.title });
                    router.push(`/meeting-details?id=${meeting.id}`);
                  }}
                  className="w-full flex items-center gap-3 p-3 bg-card border border-border rounded-lg hover:bg-accent/60 hover:border-foreground/30 transition-colors text-left"
                >
                  {selectionMode && (
                    <Checkbox
                      checked={selectedIds.has(meeting.id)}
                      onCheckedChange={() => toggleSelected(meeting.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  )}
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
      </ScrollArea>

      <ConfirmationModal
        isOpen={showDeleteConfirm}
        text={
          allSelected
            ? `This will delete the entire "${folderName}" folder and all ${selectedIds.size} meeting${selectedIds.size === 1 ? '' : 's'} in it. This action cannot be undone.`
            : `Delete ${selectedIds.size} meeting${selectedIds.size === 1 ? '' : 's'} from this folder? This action cannot be undone.`
        }
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          setShowDeleteConfirm(false);
          setDeleteRemoteChecked(false);
        }}
      >
        {anyPushedSelected && (
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <Checkbox
              checked={deleteRemoteChecked}
              onCheckedChange={(checked) => setDeleteRemoteChecked(checked === true)}
            />
            Also delete from Wusool server &amp; Attio
          </label>
        )}
      </ConfirmationModal>
    </div>
  );
}

function FolderContent() {
  const searchParams = useSearchParams();
  const tagSlug = searchParams.get('tag') ?? '';
  const folderName = searchParams.get('name') ?? 'Folder';
  // Same route for every folder, so React would otherwise reuse state (selection, search) across them.
  return <FolderView key={tagSlug} tagSlug={tagSlug} folderName={folderName} />;
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
