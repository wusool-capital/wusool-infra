'use client';

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Bug, ChevronDown, ChevronRight, File, Settings, PanelLeft, Calendar, StickyNote, Home, Trash2, Mic, Square, Plus, Search, Pencil, NotebookPen, SearchIcon, X, Upload, Folder } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { useRouter, usePathname } from 'next/navigation';
import { useSidebar, TAG_FOLDER_PREFIX } from './SidebarProvider';
import type { CurrentMeeting } from '@/components/Sidebar/SidebarProvider';
import { ConfirmationModal } from '../ConfirmationModel/confirmation-modal';
import { ModelConfig } from '@/components/ModelSettingsModal';
import { SettingTabs } from '../SettingTabs';
import { TranscriptModelProps } from '@/components/TranscriptSettings';
import Analytics from '@/lib/analytics';
import { invoke } from '@tauri-apps/api/core';
import { getVersion } from '@tauri-apps/api/app';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';
import { useRecordingState } from '@/contexts/RecordingStateContext';
import { useImportDialog } from '@/contexts/ImportDialogContext';
import { useConfig } from '@/contexts/ConfigContext';
import { useDeleteMeetings } from '@/hooks/useDeleteMeetings';
import { cn } from '@/lib/utils';
import { RollingLabel } from './RollingLabel';

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog"
import { VisuallyHidden } from "@/components/ui/visually-hidden"
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

import Logo from '../Logo';
import { ComplianceNotification } from '../ComplianceNotification';
import { FeedbackDialog } from '../FeedbackDialog';
import { Input } from '../ui/input';
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '../ui/input-group';
import { ScrollArea } from '../ui/scroll-area';

interface SidebarItem {
  id: string;
  title: string;
  type: 'folder' | 'file';
  children?: SidebarItem[];
  durationSeconds?: number | null;
  createdAt?: string | null;
  pushedAt?: string | null;
}

// e.g. 1845 -> "31m", 5400 -> "1h 30m", 12 -> "1m" (rounded up to the
// nearest minute, never down -- a 12-second meeting isn't "0m").
// null only when there's no duration to show at all (still recording,
// or no transcript segments yet).
function formatDuration(seconds?: number | null): string | null {
  if (!seconds || seconds <= 0) return null;
  const totalMinutes = Math.ceil(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

// e.g. "Aug 24" -- includes the year only when it isn't the current one.
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

const SIDEBAR_MIN_WIDTH = 256;
const SIDEBAR_MAX_VIEWPORT_RATIO = 0.7;
const SIDEBAR_WIDTH_STORAGE_KEY = 'sidebarWidth';

const Sidebar: React.FC = () => {
  const router = useRouter();
  const pathname = usePathname();
  const [appVersion, setAppVersion] = useState<string>('0.4.0');

  useEffect(() => {
    getVersion().then(setAppVersion).catch(console.error);
  }, []);

  useEffect(() => {
    try {
      const saved = Number(localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY));
      if (saved >= SIDEBAR_MIN_WIDTH) setSidebarWidth(saved);
    } catch (error) {
      console.error('Failed to load sidebar width:', error);
    }
  }, []);

  const handleResizeStart = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizing(true);
    // Body-level cursor/select overrides keep the drag smooth when the pointer leaves the thin handle.
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    let latestWidth = sidebarWidth;

    const onMove = (event: PointerEvent) => {
      const maxWidth = Math.max(SIDEBAR_MIN_WIDTH, window.innerWidth * SIDEBAR_MAX_VIEWPORT_RATIO);
      latestWidth = Math.round(Math.min(Math.max(event.clientX, SIDEBAR_MIN_WIDTH), maxWidth));
      setSidebarWidth(latestWidth);
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setIsResizing(false);
      try {
        localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(latestWidth));
      } catch (error) {
        console.error('Failed to save sidebar width:', error);
      }
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const {
    currentMeeting,
    setCurrentMeeting,
    sidebarItems,
    isCollapsed,
    toggleCollapse,
    handleRecordingToggle,
    searchTranscripts,
    searchResults,
    isSearching,
    meetings,
    setMeetings,
    serverAddress
  } = useSidebar();

  // Get recording state from RecordingStateContext (single source of truth)
  const { isRecording, isStarting } = useRecordingState();
  const { deleteMeetings } = useDeleteMeetings();
  const { openImportDialog } = useImportDialog();
  const { betaFeatures } = useConfig();
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['meetings']));
  const [sidebarWidth, setSidebarWidth] = useState<number>(SIDEBAR_MIN_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showModelSettings, setShowModelSettings] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [modelConfig, setModelConfig] = useState<ModelConfig>({
    provider: 'ollama',
    model: '',
    whisperModel: '',
    apiKey: null,
    ollamaEndpoint: null
  });
  const [transcriptModelConfig, setTranscriptModelConfig] = useState<TranscriptModelProps>({
    provider: 'parakeet',
    model: 'parakeet-tdt-0.6b-v3-int8',
  });
  const [settingsSaveSuccess, setSettingsSaveSuccess] = useState<boolean | null>(null);

  // State for edit modal
  const [editModalState, setEditModalState] = useState<{ isOpen: boolean; meetingId: string | null; currentTitle: string }>({
    isOpen: false,
    meetingId: null,
    currentTitle: ''
  });
  const [editingTitle, setEditingTitle] = useState<string>('');

  // Ensure 'meetings' folder is always expanded
  useEffect(() => {
    if (!expandedFolders.has('meetings')) {
      const newExpanded = new Set(expandedFolders);
      newExpanded.add('meetings');
      setExpandedFolders(newExpanded);
    }
  }, [expandedFolders]);

  // useEffect(() => {
  //   if (settingsSaveSuccess !== null) {
  //     const timer = setTimeout(() => {
  //       setSettingsSaveSuccess(null);
  //     }, 3000);
  //   }
  // }, [settingsSaveSuccess]);


  const [deleteModalState, setDeleteModalState] = useState<{
    isOpen: boolean;
    itemIds: string[];
    folderTitle: string | null;
    anyPushed: boolean;
  }>({ isOpen: false, itemIds: [], folderTitle: null, anyPushed: false });
  const [deleteRemoteChecked, setDeleteRemoteChecked] = useState(false);

  useEffect(() => {
    // Note: Don't set hardcoded defaults - let DB be the source of truth
    const fetchModelConfig = async () => {
      // Only make API call if serverAddress is loaded
      if (!serverAddress) {
        console.log('Waiting for server address to load before fetching model config');
        return;
      }

      try {
        const data = await invoke('api_get_model_config') as any;
        if (data && data.provider !== null) {
          // Fetch API key if not included and provider requires it
          if (data.provider !== 'ollama' && !data.apiKey) {
            try {
              const apiKeyData = await invoke('api_get_api_key', {
                provider: data.provider
              }) as string;
              data.apiKey = apiKeyData;
            } catch (err) {
              console.error('Failed to fetch API key:', err);
            }
          }
          setModelConfig(data);
        }
      } catch (error) {
        console.error('Failed to fetch model config:', error);
      }
    };

    fetchModelConfig();
  }, [serverAddress]);


  useEffect(() => {
    // Note: Don't set hardcoded defaults - let DB be the source of truth
    const fetchTranscriptSettings = async () => {
      // Only make API call if serverAddress is loaded
      if (!serverAddress) {
        console.log('Waiting for server address to load before fetching transcript settings');
        return;
      }

      try {
        const data = await invoke('api_get_transcript_config') as any;
        if (data && data.provider !== null) {
          setTranscriptModelConfig(data);
        }
      } catch (error) {
        console.error('Failed to fetch transcript settings:', error);
      }
    };
    fetchTranscriptSettings();
  }, [serverAddress]);

  // Listen for model config updates from other components
  useEffect(() => {
    const setupListener = async () => {
      const { listen } = await import('@tauri-apps/api/event');
      const unlisten = await listen<ModelConfig>('model-config-updated', (event) => {
        console.log('Sidebar received model-config-updated event:', event.payload);
        setModelConfig(event.payload);
      });

      return unlisten;
    };

    let cleanup: (() => void) | undefined;
    setupListener().then(fn => cleanup = fn);

    return () => {
      cleanup?.();
    };
  }, []);



  // Handle model config save
  const handleSaveModelConfig = async (config: ModelConfig) => {
    try {
      await invoke('api_save_model_config', {
        provider: config.provider,
        model: config.model,
        whisperModel: config.whisperModel,
        apiKey: config.apiKey,
        ollamaEndpoint: config.ollamaEndpoint,
      });

      setModelConfig(config);
      console.log('Model config saved successfully');
      setSettingsSaveSuccess(true);

      // Emit event to sync other components
      const { emit } = await import('@tauri-apps/api/event');
      await emit('model-config-updated', config);

      // Track settings change
      await Analytics.trackSettingsChanged('model_config', `${config.provider}_${config.model}`);
    } catch (error) {
      console.error('Error saving model config:', error);
      setSettingsSaveSuccess(false);
    }
  };

  const handleSaveTranscriptConfig = async (updatedConfig?: TranscriptModelProps) => {
    try {
      const configToSave = updatedConfig || transcriptModelConfig;
      const payload = {
        provider: configToSave.provider,
        model: configToSave.model,
        apiKey: configToSave.apiKey ?? null
      };
      console.log('Saving transcript config with payload:', payload);

      await invoke('api_save_transcript_config', {
        provider: payload.provider,
        model: payload.model,
        apiKey: payload.apiKey,
      });


      setSettingsSaveSuccess(true);

      // Track settings change
      const transcriptConfigToSave = updatedConfig || transcriptModelConfig;
      await Analytics.trackSettingsChanged('transcript_config', `${transcriptConfigToSave.provider}_${transcriptConfigToSave.model}`);
    } catch (error) {
      console.error('Failed to save transcript config:', error);
      setSettingsSaveSuccess(false);
    }
  };

  // Handle search input changes
  const handleSearchChange = useCallback(async (value: string) => {
    setSearchQuery(value);

    // If search query is empty, just return to normal view
    if (!value.trim()) return;

    // Search through transcripts
    await searchTranscripts(value);

    // Make sure the meetings folder is expanded when searching
    if (!expandedFolders.has('meetings')) {
      const newExpanded = new Set(expandedFolders);
      newExpanded.add('meetings');
      setExpandedFolders(newExpanded);
    }
  }, [expandedFolders, searchTranscripts]);

  // Recursively filter the (possibly nested, tag-folder) sidebar tree by
  // search query / transcript search results. A folder survives if any
  // descendant survives, or if its own title matches -- so a match deep
  // inside a tag folder still keeps that folder (and its ancestors) visible.
  const filterItemsRecursive = useCallback(
    (items: SidebarItem[]): SidebarItem[] => {
      if (!searchQuery.trim()) return items;
      const matchedMeetingIds = new Set(searchResults.map(result => result.id));
      const query = searchQuery.toLowerCase();

      return items
        .map(item => {
          if (item.type === 'folder') {
            const filteredChildren = item.children ? filterItemsRecursive(item.children) : [];
            if (filteredChildren.length > 0 || item.title.toLowerCase().includes(query)) {
              return { ...item, children: filteredChildren };
            }
            return undefined;
          }
          return matchedMeetingIds.has(item.id) || item.title.toLowerCase().includes(query)
            ? item
            : undefined;
        })
        .filter((item): item is SidebarItem => item !== undefined);
    },
    [searchQuery, searchResults]
  );

  const filteredSidebarItems = useMemo(
    () => filterItemsRecursive(sidebarItems),
    [sidebarItems, filterItemsRecursive]
  );

  // While searching, auto-expand every folder that survived filtering
  // (i.e. contains a match) regardless of its collapsed/expanded state,
  // so matches inside a collapsed tag folder are still visible.
  const searchExpandedFolderIds = useMemo(() => {
    const ids = new Set<string>();
    if (!searchQuery.trim()) return ids;
    const walk = (items: SidebarItem[]) => {
      for (const item of items) {
        if (item.type === 'folder') {
          ids.add(item.id);
          if (item.children) walk(item.children);
        }
      }
    };
    walk(filteredSidebarItems);
    return ids;
  }, [filteredSidebarItems, searchQuery]);


  const handleDeleteConfirm = () => {
    if (deleteModalState.itemIds.length > 0) {
      deleteMeetings(deleteModalState.itemIds, deleteModalState.anyPushed && deleteRemoteChecked);
    }
    setDeleteModalState({ isOpen: false, itemIds: [], folderTitle: null, anyPushed: false });
    setDeleteRemoteChecked(false);
  };

  // Handle modal editing of meeting names
  const handleEditStart = (meetingId: string, currentTitle: string) => {
    setEditModalState({
      isOpen: true,
      meetingId: meetingId,
      currentTitle: currentTitle
    });
    setEditingTitle(currentTitle);
  };

  const handleEditConfirm = async () => {
    const newTitle = editingTitle.trim();
    const meetingId = editModalState.meetingId;

    if (!meetingId) return;

    // Prevent empty titles
    if (!newTitle) {
      toast.error("Meeting title cannot be empty");
      return;
    }

    try {
      await invoke('api_save_meeting_title', {
        meetingId: meetingId,
        title: newTitle,
      });

      // Update local state
      const updatedMeetings = meetings.map((m: CurrentMeeting) =>
        m.id === meetingId ? { ...m, title: newTitle } : m
      );
      setMeetings(updatedMeetings);

      // Update current meeting if it's the one being edited
      if (currentMeeting?.id === meetingId) {
        setCurrentMeeting({ id: meetingId, title: newTitle });
      }

      // Track the edit
      Analytics.trackButtonClick('edit_meeting_title', 'sidebar');

      toast.success("Meeting title updated successfully");

      // Close modal and reset state
      setEditModalState({ isOpen: false, meetingId: null, currentTitle: '' });
      setEditingTitle('');
    } catch (error) {
      console.error('Failed to update meeting title:', error);
      toast.error("Failed to update meeting title", {
        description: error instanceof Error ? error.message : String(error)
      });
    }
  };

  const handleEditCancel = () => {
    setEditModalState({ isOpen: false, meetingId: null, currentTitle: '' });
    setEditingTitle('');
  };

  const toggleFolder = (folderId: string) => {
    // Normal toggle behavior for all folders
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(folderId)) {
      newExpanded.delete(folderId);
    } else {
      newExpanded.add(folderId);
    }
    setExpandedFolders(newExpanded);
  };

  // Expose setShowModelSettings to window for Rust tray to call
  useEffect(() => {
    (window as any).openSettings = () => {
      setShowModelSettings(true);
    };

    // Cleanup on unmount
    return () => {
      delete (window as any).openSettings;
    };
  }, []);

  const renderCollapsedIcons = () => {
    if (!isCollapsed) return null;

    const isHomePage = pathname === '/';
    const isMeetingPage = pathname?.includes('/meeting-details');
    const isSettingsPage = pathname === '/settings';

    return (
      <TooltipProvider>
        <div className="flex flex-col items-center space-y-4 mt-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleCollapse}
                className="rounded-lg text-muted-foreground"
              >
                <PanelLeft className="w-5 h-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>Expand sidebar</p>
            </TooltipContent>
          </Tooltip>

          <Logo isCollapsed={isCollapsed} />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => router.push('/')}
                className={cn('rounded-lg text-muted-foreground', isHomePage && 'bg-accent text-accent-foreground')}
              >
                <Home className="w-5 h-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>Home</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="destructive"
                size="icon"
                onClick={handleRecordingToggle}
                disabled={isRecording || isStarting}
                className="rounded-full shadow-sm"
              >
                {isStarting ? (
                  <Spinner className="w-5 h-5" />
                ) : isRecording ? (
                  <Square className="w-5 h-5" />
                ) : (
                  <Mic className="w-5 h-5" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>{isStarting ? "Starting..." : isRecording ? "Recording in progress..." : "Start Recording"}</p>
            </TooltipContent>
          </Tooltip>

          {betaFeatures.importAndRetranscribe && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => openImportDialog()}
                  className="rounded-lg bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary"
                >
                  <Upload className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>Import Audio</p>
              </TooltipContent>
            </Tooltip>
          )}

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  if (isCollapsed) toggleCollapse();
                  toggleFolder('meetings');
                }}
                className={cn('rounded-lg text-muted-foreground', isMeetingPage && 'bg-accent text-accent-foreground')}
              >
                <NotebookPen className="w-5 h-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>Meeting Notes</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => router.push('/settings')}
                className={cn('rounded-lg text-muted-foreground', isSettingsPage && 'bg-accent text-accent-foreground')}
              >
                <Settings className="w-5 h-5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>Settings</p>
            </TooltipContent>
          </Tooltip>

        </div>
      </TooltipProvider>
    );
  };

  // Find matching transcript snippet for a meeting item
  const findMatchingSnippet = (itemId: string) => {
    if (!searchQuery.trim() || !searchResults.length) return null;
    return searchResults.find(result => result.id === itemId);
  };

  const renderItem = (item: SidebarItem, depth = 0) => {
    const isExpanded = expandedFolders.has(item.id) || searchExpandedFolderIds.has(item.id);
    const paddingLeft = `${depth * 12 + 12}px`;
    // currentMeeting outlives the meeting page, so it only counts while one is open.
    const onMeetingRoute = !!pathname && (pathname.startsWith('/meeting-details') || pathname.startsWith('/notes'));
    const isActive = onMeetingRoute && item.type === 'file' && currentMeeting?.id === item.id;
    const isMeetingItem = item.id.includes('-') && !item.id.startsWith('intro-call');

    // Check if this item has a matching transcript snippet
    const matchingResult = isMeetingItem ? findMatchingSnippet(item.id) : null;
    const hasTranscriptMatch = !!matchingResult;

    if (isCollapsed) return null;

    return (
      <div key={item.id}>
        <div
          className={cn(
            'flex items-center transition-colors duration-150 group',
            item.type === 'folder' && depth === 0
              ? 'h-8 mx-3 mt-1 px-2 rounded-md text-xs font-semibold uppercase tracking-wide text-muted-foreground/80 hover:bg-accent/50 hover:text-foreground cursor-pointer'
              : cn(
                  'px-2.5 py-2 my-0.5 rounded-lg text-sm cursor-pointer',
                  isActive
                    ? 'bg-primary/10 text-primary font-medium'
                    : 'hover:bg-accent/60'
                )
          )}
          style={item.type === 'folder' && depth === 0 ? {} : { paddingLeft }}
          onClick={() => {
            if (item.type === 'folder') {
              if (item.id.startsWith(TAG_FOLDER_PREFIX)) {
                router.push(`/folder?tag=${encodeURIComponent(item.id.slice(TAG_FOLDER_PREFIX.length))}&name=${encodeURIComponent(item.title)}`);
              } else {
                toggleFolder(item.id);
              }
            } else {
              setCurrentMeeting({ id: item.id, title: item.title });
              const basePath = item.id.startsWith('intro-call') ? '/' :
                item.id.includes('-') ? `/meeting-details?id=${item.id}` : `/notes/${item.id}`;
              router.push(basePath);
            }
          }}
        >
          {item.type === 'folder' ? (
            <>
              {item.id === 'meetings' ? (
                <Calendar className="w-4 h-4 mr-2" />
              ) : item.id === 'notes' ? (
                <Calendar className="w-4 h-4 mr-2" />
              ) : (
                <Folder className="w-4 h-4 mr-2 text-muted-foreground" />
              )}
              <RollingLabel text={item.title} className={cn('mr-2', depth !== 0 && 'font-medium')} />
              {item.id.startsWith(TAG_FOLDER_PREFIX) && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 ml-auto flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150 hover:text-destructive hover:bg-destructive/10"
                  onClick={(e) => {
                    e.stopPropagation();
                    const children = item.children ?? [];
                    setDeleteModalState({
                      isOpen: true,
                      itemIds: children.map((child) => child.id),
                      folderTitle: item.title,
                      anyPushed: children.some((child) => !!child.pushedAt),
                    });
                  }}
                  aria-label="Delete folder"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
              <div className={cn(item.id.startsWith(TAG_FOLDER_PREFIX) ? 'ml-1' : 'ml-auto')}>
                {item.id.startsWith(TAG_FOLDER_PREFIX) ? (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                ) : isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
              {searchQuery && item.id === 'meetings' && isSearching && (
                <span className="ml-2 text-xs text-primary animate-pulse">Searching...</span>
              )}
            </>
          ) : (
            <div className="flex flex-col w-full">
              <div className="flex items-center w-full">
                {isMeetingItem ? (
                  <div className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full mr-2 bg-muted">
                    <File className="w-3.5 h-3.5 text-muted-foreground" />
                  </div>
                ) : (
                  <div className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full mr-2 bg-primary/10">
                    <Plus className="w-3.5 h-3.5 text-primary" />
                  </div>
                )}
                <span className="flex-1 truncate min-w-0" title={item.title}>{item.title}</span>
                {isMeetingItem && (formatMeetingDate(item.createdAt) || formatDuration(item.durationSeconds)) && (
                  <span className="flex-shrink-0 ml-2 text-xs text-muted-foreground whitespace-nowrap">
                    {[formatMeetingDate(item.createdAt), formatDuration(item.durationSeconds)]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                )}
                {isMeetingItem && (
                  <div className="flex items-center gap-1 ml-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 flex-shrink-0 hover:text-primary hover:bg-primary/10"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditStart(item.id, item.title);
                      }}
                      aria-label="Edit meeting title"
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 flex-shrink-0 hover:text-destructive hover:bg-destructive/10"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteModalState({
                          isOpen: true,
                          itemIds: [item.id],
                          folderTitle: null,
                          anyPushed: !!item.pushedAt,
                        });
                      }}
                      aria-label="Delete meeting"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>

              {/* Show transcript match snippet if available */}
              {hasTranscriptMatch && (
                <div className="mt-1.5 ml-8 mr-1 rounded-md border-l-2 border-primary/40 bg-muted/60 py-1.5 pl-2.5 pr-2">
                  <p className="text-[11px] leading-snug text-muted-foreground line-clamp-2">
                    <span className="font-medium text-foreground/80">Match: </span>
                    {matchingResult.matchContext}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
        {item.type === 'folder' && isExpanded && item.children && (
          <div className="ml-1">
            {item.children.map(child => renderItem(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-screen flex-shrink-0 relative">
      <div
        className={cn(
          'h-screen bg-muted/40 shadow-sm flex flex-col text-foreground',
          !isResizing && 'transition-all duration-300',
          isCollapsed && 'w-16'
        )}
        // maxWidth re-clamps a saved width when the window later shrinks.
        style={isCollapsed ? undefined : { width: sidebarWidth, minWidth: SIDEBAR_MIN_WIDTH, maxWidth: `${SIDEBAR_MAX_VIEWPORT_RATIO * 100}vw` }}
      >
        {/*  Header with traffic light spacing */}
        <div className="flex-shrink-0">
          {isCollapsed ? (
            <div className="h-2" />
          ) : (
            <div className="px-3 pt-6 pb-3">
              <div className="flex items-center mb-3">
                <Logo isCollapsed={isCollapsed} />
                <TooltipProvider>
                  <div className="ml-auto flex items-center gap-0.5 flex-shrink-0">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setShowFeedback(true)}
                          className="h-10 w-10 rounded-lg text-muted-foreground"
                        >
                          <Bug className="w-5 h-5" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="bottom">
                        <p>Send feedback</p>
                      </TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={toggleCollapse}
                          className="h-10 w-10 rounded-lg text-muted-foreground"
                        >
                          <PanelLeft className="w-5 h-5" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right">
                        <p>Collapse sidebar</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </TooltipProvider>
              </div>

              <div className="relative">
                <InputGroup >
                  <InputGroupInput placeholder='Search meeting content...' value={searchQuery}
                    onChange={(e) => handleSearchChange(e.target.value)}
                  />
                  <InputGroupAddon>
                    <SearchIcon />
                  </InputGroupAddon>
                  {searchQuery &&
                    <InputGroupAddon align={'inline-end'}>
                      <InputGroupButton
                        onClick={() => handleSearchChange('')}
                      >
                        <X />
                      </InputGroupButton>
                    </InputGroupAddon>
                  }
                </InputGroup>
              </div>
            </div>
          )}
        </div>

        {/* Main content - scrollable area */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Fixed navigation items */}
          <div className="flex-shrink-0">
            {!isCollapsed && (
              <div className="px-3 pt-1">
                <div
                  onClick={() => router.push('/')}
                  className={cn(
                    'flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-sm font-medium cursor-pointer transition-colors',
                    pathname === '/'
                      ? 'bg-primary/10 text-primary'
                      : 'text-foreground/80 hover:bg-accent/60 hover:text-foreground'
                  )}
                >
                  <Home className="w-4 h-4" />
                  <span>Home</span>
                </div>
              </div>
            )}
          </div>

          {/* Content area */}
          <div className="flex-1 flex flex-col min-h-0">
            {renderCollapsedIcons()}
            {/* Meeting Notes folder header - fixed */}
            {!isCollapsed && (
              <div className="flex-shrink-0">
                {filteredSidebarItems.filter(item => item.type === 'folder').map(item => (
                  <div
                    key={item.id}
                    className="flex items-center gap-1.5 px-4 pt-5 pb-1.5"
                  >
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                      {item.title}
                    </span>
                    {searchQuery && item.id === 'meetings' && isSearching && (
                      <span className="text-[11px] text-primary animate-pulse">Searching...</span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Scrollable meeting items */}
            {!isCollapsed && (
              <ScrollArea className="flex-1 min-h-0">
                {filteredSidebarItems
                  .filter(item => item.type === 'folder' && expandedFolders.has(item.id) && item.children)
                  .map(item => (
                    <div key={`${item.id}-children`} className="mx-3">
                      {item.children!.map(child => renderItem(child, 1))}
                    </div>
                  ))}
              </ScrollArea>
            )}
          </div>
        </div>

        {/* Footer */}
        {!isCollapsed && (

          <div className="flex-shrink-0 p-2 pt-3 space-y-1.5 border-t border-border/60">
            <Button
              variant="destructive"
              onClick={handleRecordingToggle}
              disabled={isRecording || isStarting}
              className="w-full shadow-sm"
            >
              {isStarting ? (
                <>
                  <Spinner className="w-4 h-4 mr-2" />
                  <span>Starting...</span>
                </>
              ) : isRecording ? (
                <>
                  <Square className="w-4 h-4 mr-2" />
                  <span>Recording in progress...</span>
                </>
              ) : (
                <>
                  <Mic className="w-4 h-4 mr-2" />
                  <span>Start Recording</span>
                </>
              )}
            </Button>

            {betaFeatures.importAndRetranscribe && (
              <Button
                variant="ghost"
                onClick={() => openImportDialog()}
                className="w-full bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary shadow-sm"
              >
                <Upload className="w-4 h-4 mr-2" />
                <span>Import Audio</span>
              </Button>
            )}

            <Button
              variant="secondary"
              onClick={() => router.push('/settings')}
              className="w-full shadow-sm"
            >
              <Settings className="w-4 h-4 mr-2" />
              <span>Settings</span>
            </Button>
            <div className="w-full flex items-center justify-center pt-0.5 text-[11px] text-muted-foreground/70">
              v{appVersion}
            </div>
          </div>
        )}
      </div>

      {!isCollapsed && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          onPointerDown={handleResizeStart}
          className={cn(
            'absolute top-0 right-0 h-full w-1.5 -mr-0.5 cursor-col-resize z-10 transition-colors hover:bg-primary/30',
            isResizing && 'bg-primary/40'
          )}
        />
      )}

      {/* Confirmation Modal for Delete */}
      <ConfirmationModal
        isOpen={deleteModalState.isOpen}
        text={deleteModalState.folderTitle
          ? `Are you sure you want to delete the folder "${deleteModalState.folderTitle}" and all ${deleteModalState.itemIds.length} meeting${deleteModalState.itemIds.length === 1 ? '' : 's'} in it? This action cannot be undone.`
          : "Are you sure you want to delete this meeting? This action cannot be undone."}
        onConfirm={handleDeleteConfirm}
        onCancel={() => {
          setDeleteModalState({ isOpen: false, itemIds: [], folderTitle: null, anyPushed: false });
          setDeleteRemoteChecked(false);
        }}
      >
        {deleteModalState.anyPushed && (
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <Checkbox
              checked={deleteRemoteChecked}
              onCheckedChange={(checked) => setDeleteRemoteChecked(checked === true)}
            />
            Also delete from Wusool server &amp; Attio
          </label>
        )}
      </ConfirmationModal>

      {/* Edit Meeting Title Modal */}
      <Dialog open={editModalState.isOpen} onOpenChange={(open) => {
        if (!open) handleEditCancel();
      }}>
        <DialogContent className="sm:max-w-[425px]">
          <VisuallyHidden>
            <DialogTitle>Edit Meeting Title</DialogTitle>
          </VisuallyHidden>
          <div className="py-4">
            <h3 className="text-lg font-semibold mb-4">Edit Meeting Title</h3>
            <div className="space-y-4">
              <div>
                <label htmlFor="meeting-title" className="block text-sm font-medium text-foreground mb-2">
                  Meeting Title
                </label>
                <Input
                  id="meeting-title"
                  type="text"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleEditConfirm();
                    } else if (e.key === 'Escape') {
                      handleEditCancel();
                    }
                  }}
                  placeholder="Enter meeting title"
                  autoFocus
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={handleEditCancel}>
              Cancel
            </Button>
            <Button onClick={handleEditConfirm}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <FeedbackDialog open={showFeedback} onOpenChange={setShowFeedback} />
    </div>
  );
};

export default Sidebar;
