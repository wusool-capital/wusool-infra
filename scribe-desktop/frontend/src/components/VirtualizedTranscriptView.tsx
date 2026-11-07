'use client';

import { useCallback, useRef, useReducer, startTransition, useEffect, useLayoutEffect, useState, memo } from "react";
import { cn } from "@/lib/utils";
import { Textarea } from "./ui/textarea";
import { Spinner } from "./ui/spinner";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { useTranscriptStreaming } from "@/hooks/useTranscriptStreaming";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { motion } from "framer-motion";
import { SpeakerLabel, TranscriptSegmentData } from "@/types";
import type { SpeakerNames } from "@/hooks/useMeetingSpeakers";
import { SpeakerChip } from "./SpeakerChip";
import { ScrollArea } from "./ui/scroll-area";
import { Checkbox } from "./ui/checkbox";
import { Button } from "./ui/button";
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuSeparator,
    ContextMenuTrigger,
} from "./ui/context-menu";
import { Check, X } from "lucide-react";
import { CorrectionSuggestion, SelectMode, diffSpan } from "@/lib/transcriptEditor";
import type { TranscriptEditorApi } from "@/hooks/meeting-details/useTranscriptEditor";

export interface VirtualizedTranscriptViewProps {
    /** Transcript segments to display */
    segments: TranscriptSegmentData[];
    /** Whether recording is in progress */
    isRecording?: boolean;
    /** Whether recording is paused */
    isPaused?: boolean;
    /** Whether processing/finalizing transcription */
    isProcessing?: boolean;
    /** Whether stopping */
    isStopping?: boolean;
    /** Enable streaming effect for latest segment */
    enableStreaming?: boolean;
    /** Show confidence indicators */
    showConfidence?: boolean;
    /** Completely disable auto-scroll behavior (for meeting details page) */
    disableAutoScroll?: boolean;

    // Pagination props (infinite scroll)
    hasMore?: boolean;
    isLoadingMore?: boolean;
    totalCount?: number;
    loadedCount?: number;
    onLoadMore?: () => void;

    /** Allow editing segment text -- false once the meeting is pushed. */
    editable?: boolean;
    /** Called on blur with the segment id and its edited text. */
    onEditSegment?: (id: string, text: string) => void | Promise<unknown>;
    /** Selection, bulk edit and suggestion actions; only used when `editable`. */
    editor?: TranscriptEditorApi;
    /** Resolves and renames speakers; segments show no speaker without it. */
    speakers?: SpeakerNames;
    /** Shown when there are no lines and nothing is recording. */
    emptyState?: React.ReactNode;
}

// Threshold for enabling virtualization (below this, use simple rendering)
const VIRTUALIZATION_THRESHOLD = 10;

/** Recording-relative time as m:ss (h:mm:ss past an hour), or null when unknown. */
function formatRecordingTime(seconds: number | undefined): string | null {
    if (seconds === undefined) return null;
    const total = Math.floor(seconds);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = (total % 60).toString().padStart(2, '0');
    return hours > 0 ? `${hours}:${minutes.toString().padStart(2, '0')}:${secs}` : `${minutes}:${secs}`;
}

/** Grows a textarea to fit its text, refitting when the column width changes. */
function useAutosize(ref: React.RefObject<HTMLTextAreaElement>, value: string) {
    useLayoutEffect(() => {
        const el = ref.current;
        if (!el) return;
        const fit = () => {
            el.style.height = 'auto';
            // scrollHeight leaves out the borders, which border-box sizing counts in height.
            const borders = el.offsetHeight - el.clientHeight;
            el.style.height = `${el.scrollHeight + borders}px`;
        };
        fit();
        // Watch width only: refitting on height changes would feed back into itself.
        let lastWidth = el.clientWidth;
        const observer = new ResizeObserver(() => {
            if (el.clientWidth !== lastWidth) {
                lastWidth = el.clientWidth;
                fit();
            }
        });
        observer.observe(el);
        return () => observer.disconnect();
    }, [ref, value]);
}

function SuggestionDiff({
    suggestion,
    onAccept,
    onDismiss,
}: {
    suggestion: CorrectionSuggestion;
    onAccept: () => void;
    onDismiss: () => void;
}) {
    const { removed, added } = diffSpan(suggestion.original, suggestion.suggested);
    return (
        <div className="mx-2 mt-1 flex items-center gap-3 rounded-md bg-muted px-3 py-1.5 text-sm">
            <div className="min-w-0 flex-1 leading-relaxed">
                {removed && <del className="text-destructive">{removed}</del>}
                {removed && added && <span className="text-muted-foreground"> → </span>}
                {added && <ins className="font-medium text-success no-underline">{added}</ins>}
                <span className="ml-2 text-muted-foreground">{suggestion.reason}</span>
            </div>
            <Button size="sm" variant="ghost" className="h-7 px-2" onClick={onAccept}>
                <Check />
                Accept
            </Button>
            <Button size="sm" variant="ghost" className="h-7 px-2 text-muted-foreground" onClick={onDismiss}>
                <X />
                Dismiss
            </Button>
        </div>
    );
}

// Memoized transcript segment component
const TranscriptSegment = memo(function TranscriptSegment({
    id,
    timestamp,
    text,
    confidence,
    isStreaming,
    showConfidence,
    editable,
    onEditSegment,
    selected,
    selectionActive,
    onSelect,
    suggestion,
    onAcceptSuggestion,
    onDismissSuggestion,
    onDeleteBefore,
    onMergeWithNext,
    onSplit,
    speaker,
    showSpeaker,
    isFirst,
    speakers,
}: {
    id: string;
    timestamp: number;
    text: string;
    confidence?: number;
    isStreaming: boolean;
    showConfidence: boolean;
    editable?: boolean;
    onEditSegment?: (id: string, text: string) => void | Promise<unknown>;
    selected?: boolean;
    /** Any line is selected, so every checkbox stays visible. */
    selectionActive?: boolean;
    onSelect?: (id: string, mode: SelectMode) => void;
    suggestion?: CorrectionSuggestion;
    onAcceptSuggestion?: (suggestion: CorrectionSuggestion) => void;
    onDismissSuggestion?: (segmentId: string) => void;
    onDeleteBefore?: (id: string) => void;
    onMergeWithNext?: (id: string) => void;
    onSplit?: (id: string, cursor: number) => void;
    speaker?: SpeakerLabel | null;
    showSpeaker: boolean;
    isFirst: boolean;
    speakers?: SpeakerNames;
}) {
    const [draft, setDraft] = useState(text);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    useAutosize(textareaRef, draft);

    // Keep the draft in sync if the underlying segment text changes from
    // outside this component (e.g. a fresh fetch after push).
    useEffect(() => setDraft(text), [text]);

    const selectable = Boolean(editable && onSelect);
    const time = formatRecordingTime(timestamp);
    const speakerLabel = showSpeaker && speaker && speakers ? speaker : null;
    const speakerName = speaker && speakers ? speakers.resolveName(speaker) : null;
    // A new speaker's turn opens with more space than lines within one turn.
    const spacing = isFirst ? '' : speakerLabel ? 'pt-4' : speaker ? 'pt-0.5' : 'pt-2';
    // With a name on the first line the time and checkbox align to it; otherwise to the text.
    const firstLine = speakerLabel ? 'leading-5' : 'mt-1 leading-[26px]';

    const selectMode = (e: React.MouseEvent): SelectMode =>
        e.shiftKey ? 'range' : e.metaKey || e.ctrlKey ? 'toggle' : 'single';

    const handleSplit = async () => {
        // selectionStart counts UTF-16 units; the backend splits on code points.
        const cursor = Array.from(draft.slice(0, textareaRef.current?.selectionStart ?? 0)).length;
        // Split works on stored text, so flush any unsaved typing first.
        if (draft !== text) await onEditSegment?.(id, draft);
        onSplit?.(id, cursor);
    };

    const timeLabel = time ?? '—';
    const timeCell = selectable ? (
        <button
            type="button"
            aria-label={`Select line at ${timeLabel}`}
            className={cn(
                'rounded-sm text-right text-xs text-muted-foreground tabular-nums hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                firstLine,
            )}
            onClick={(e) => onSelect?.(id, selectMode(e))}
        >
            {timeLabel}
        </button>
    ) : (
        <span className={cn('text-right text-xs text-muted-foreground tabular-nums', firstLine)}>{timeLabel}</span>
    );

    const row = (
        <div id={`segment-${id}`} className={spacing}>
            <div
                className={cn(
                    'group grid items-start gap-x-2 rounded-md',
                    selectable ? 'grid-cols-[1rem_2.75rem_minmax(0,1fr)]' : 'grid-cols-[2.75rem_minmax(0,1fr)]',
                    selected && 'bg-muted',
                )}
            >
                {selectable && (
                    <Checkbox
                        checked={selected}
                        aria-label={`Select line at ${timeLabel}`}
                        className={cn(
                            'select-none border-muted-foreground/60 shadow-none transition-opacity data-[state=checked]:border-foreground data-[state=checked]:bg-foreground data-[state=checked]:text-background',
                            speakerLabel ? 'mt-0.5' : 'mt-[9px]',
                            // Hidden until wanted: on hover, keyboard focus, or once a selection exists.
                            selected || selectionActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus-visible:opacity-100',
                        )}
                        onClick={(e) => onSelect?.(id, e.shiftKey ? 'range' : 'toggle')}
                    />
                )}
                {confidence !== undefined && showConfidence ? (
                    <Tooltip>
                        <TooltipTrigger asChild>{timeCell}</TooltipTrigger>
                        <TooltipContent>
                            <ConfidenceIndicator confidence={confidence} showIndicator={showConfidence} />
                        </TooltipContent>
                    </Tooltip>
                ) : (
                    timeCell
                )}
                <div className="min-w-0">
                    {speakerLabel && speakers && (
                        <div className="px-2 leading-5">
                            <SpeakerChip label={speakerLabel} speakers={speakers} />
                        </div>
                    )}
                    {editable ? (
                        <Textarea
                            ref={textareaRef}
                            value={draft}
                            rows={1}
                            aria-label={`Line at ${timeLabel}${speakerName ? `, ${speakerName}` : ''}`}
                            placeholder="No speech"
                            onChange={(e) => setDraft(e.target.value)}
                            onBlur={() => {
                                if (draft !== text) onEditSegment?.(id, draft);
                            }}
                            className="min-h-0 resize-none overflow-hidden border-transparent bg-transparent px-2 py-1 text-base leading-relaxed shadow-none hover:border-border focus-visible:border-input focus-visible:ring-0 md:text-base"
                        />
                    ) : (
                        <p
                            className={cn(
                                'select-text px-2 py-1 text-base leading-relaxed break-words',
                                isStreaming ? 'rounded-md bg-muted text-foreground' : 'text-foreground',
                            )}
                        >
                            {text.trim() === '' ? <span className="text-muted-foreground">No speech</span> : text}
                        </p>
                    )}
                    {editable && suggestion && (
                        <SuggestionDiff
                            suggestion={suggestion}
                            onAccept={() => onAcceptSuggestion?.(suggestion)}
                            onDismiss={() => onDismissSuggestion?.(id)}
                        />
                    )}
                </div>
            </div>
        </div>
    );

    if (!selectable) return row;

    return (
        <ContextMenu>
            <ContextMenuTrigger asChild>{row}</ContextMenuTrigger>
            <ContextMenuContent>
                <ContextMenuItem onSelect={() => onDeleteBefore?.(id)}>
                    Delete Everything Before This Line
                </ContextMenuItem>
                <ContextMenuSeparator />
                <ContextMenuItem onSelect={() => onMergeWithNext?.(id)}>Merge With Next Line</ContextMenuItem>
                <ContextMenuItem onSelect={handleSplit}>Split at Cursor</ContextMenuItem>
            </ContextMenuContent>
        </ContextMenu>
    );
});

export const VirtualizedTranscriptView: React.FC<VirtualizedTranscriptViewProps> = ({
    segments,
    isRecording = false,
    isPaused = false,
    enableStreaming = false,
    showConfidence = true,
    disableAutoScroll = false,
    hasMore = false,
    isLoadingMore = false,
    totalCount = 0,
    loadedCount = 0,
    onLoadMore,
    editable = false,
    onEditSegment,
    editor,
    speakers,
    emptyState,
}) => {
    // Create scroll ref first - shared between virtualizer and auto-scroll hook
    const scrollRef = useRef<HTMLDivElement>(null);
    // Ref for infinite scroll trigger element
    const loadMoreTriggerRef = useRef<HTMLDivElement>(null);

    // Force re-render without flushSync (avoids React warning)
    const [, rerender] = useReducer((x: number) => x + 1, 0);

    // Setup virtualizer for efficient rendering of large lists
    const virtualizer = useVirtualizer({
        count: segments.length,
        getScrollElement: () => scrollRef.current,
        estimateSize: () => 60, // Estimated height per segment
        overscan: 10, // Render extra items above/below viewport
        onChange: () => {
            startTransition(() => {
                rerender();
            });
        },
    });

    // Custom hook for auto-scrolling (supports both virtualized and non-virtualized)
    useAutoScroll({
        scrollRef,
        segments,
        isRecording,
        isPaused,
        virtualizer,
        virtualizationThreshold: VIRTUALIZATION_THRESHOLD,
        disableAutoScroll,
    });

    // Streaming text effect hook (typewriter animation for new transcripts)
    const { streamingSegmentId, getDisplayText } = useTranscriptStreaming(
        segments,
        isRecording,
        enableStreaming
    );

    const renderSegment = (segment: TranscriptSegmentData, isStreaming: boolean, index: number) => (
        <TranscriptSegment
            id={segment.id}
            speaker={segment.speaker}
            // Only label the first line of each speaker's turn, like a chat transcript.
            showSpeaker={index === 0 || segments[index - 1]?.speaker !== segment.speaker}
            isFirst={index === 0}
            speakers={speakers}
            timestamp={segment.timestamp}
            text={getDisplayText(segment)}
            confidence={segment.confidence}
            isStreaming={isStreaming}
            showConfidence={showConfidence}
            editable={editable}
            onEditSegment={editor?.editText ?? onEditSegment}
            selected={editor?.selectedIds.has(segment.id)}
            selectionActive={(editor?.selectedIds.size ?? 0) > 0}
            onSelect={editor?.select}
            suggestion={editor?.suggestions.get(segment.id)}
            onAcceptSuggestion={editor?.acceptSuggestion}
            onDismissSuggestion={editor?.dismissSuggestion}
            onDeleteBefore={editor?.deleteBefore}
            onMergeWithNext={editor?.mergeWithNext}
            onSplit={editor?.splitAt}
        />
    );

    // Infinite scroll: IntersectionObserver to trigger loading more
    useEffect(() => {
        if (!onLoadMore || !hasMore || isLoadingMore || isRecording || segments.length === 0) {
            return;
        }

        const triggerElement = loadMoreTriggerRef.current;
        if (!triggerElement) return;

        const observer = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting && hasMore && !isLoadingMore) {
                    onLoadMore();
                }
            },
            {
                root: null,
                rootMargin: '100px',
                threshold: 0,
            }
        );

        observer.observe(triggerElement);

        return () => observer.disconnect();
    }, [hasMore, isLoadingMore, onLoadMore, isRecording, segments.length]);

    // Scroll-based fallback for fast scrolling
    useEffect(() => {
        if (!onLoadMore || !hasMore || isLoadingMore || isRecording) return;

        const scrollElement = scrollRef.current;
        if (!scrollElement) return;

        let ticking = false;

        const handleScroll = () => {
            if (ticking || isLoadingMore || !hasMore) return;

            ticking = true;
            requestAnimationFrame(() => {
                const { scrollTop, scrollHeight, clientHeight } = scrollElement;
                const scrollBottom = scrollHeight - scrollTop - clientHeight;

                // Trigger load when within 200px of bottom
                if (scrollBottom < 200 && hasMore && !isLoadingMore) {
                    onLoadMore();
                }
                ticking = false;
            });
        };

        scrollElement.addEventListener('scroll', handleScroll, { passive: true });
        return () => scrollElement.removeEventListener('scroll', handleScroll);
    }, [onLoadMore, hasMore, isLoadingMore, isRecording]);

    // Use simple rendering for small lists, virtualization for large lists
    const useVirtualization = segments.length >= VIRTUALIZATION_THRESHOLD;

    return (
        <ScrollArea viewportRef={scrollRef} className="h-full min-h-0 [&>div>div]:!block">
            <div className="flex flex-col px-4 py-2">
            <div>
            {segments.length === 0 ? (
                // Recording status lives in the controls, so the empty list says one quiet thing.
                isRecording ? (
                    <p className="mt-8 text-center text-sm text-muted-foreground" aria-live="polite">
                        {isPaused ? 'Paused. Resume to keep transcribing.' : 'Listening. Lines appear here as people speak.'}
                    </p>
                ) : (
                    emptyState ?? <p className="mt-8 text-center text-sm text-muted-foreground">No transcript yet.</p>
                )
            ) : useVirtualization ? (
                // Virtualized rendering for large lists
                <>
                    <div
                        style={{
                            height: virtualizer.getTotalSize(),
                            width: "100%",
                            position: "relative",
                        }}
                    >
                        {virtualizer.getVirtualItems().map((virtualRow) => {
                            const segment = segments[virtualRow.index];
                            const isStreaming = streamingSegmentId === segment.id;

                            return (
                                <div
                                    key={segment.id}
                                    data-index={virtualRow.index}
                                    ref={virtualizer.measureElement}
                                    style={{
                                        position: "absolute",
                                        top: 0,
                                        left: 0,
                                        width: "100%",
                                        transform: `translateY(${virtualRow.start}px)`,
                                    }}
                                >
                                    {renderSegment(segment, isStreaming, virtualRow.index)}
                                </div>
                            );
                        })}
                    </div>

                    {/* Infinite scroll trigger and loading indicator */}
                    {(hasMore || isLoadingMore) && !isRecording && segments.length > 0 && (
                        <div ref={loadMoreTriggerRef} className="flex justify-center items-center py-4 mt-2">
                            {isLoadingMore ? (
                                <div className="flex items-center gap-2 text-muted-foreground ">
                                    <Spinner className="w-4 h-4" />
                                    <span className="text-sm">Loading more…</span>
                                </div>
                            ) : hasMore && totalCount > 0 ? (
                                <span className="text-sm text-muted-foreground ">
                                    Showing {loadedCount} of {totalCount} segments
                                </span>
                            ) : null}
                        </div>
                    )}
                </>
            ) : (
                // Simple rendering for small lists (better animations)
                <>
                    <div className="space-y-1">
                        {segments.map((segment, index) => {
                            const isStreaming = streamingSegmentId === segment.id;

                            return (
                                <motion.div
                                    key={segment.id}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.15 }}
                                >
                                    {renderSegment(segment, isStreaming, index)}
                                </motion.div>
                            );
                        })}
                    </div>

                    {/* Infinite scroll trigger (for small lists that grow) */}
                    {(hasMore || isLoadingMore) && !isRecording && segments.length > 0 && (
                        <div ref={loadMoreTriggerRef} className="flex justify-center items-center py-4 mt-2">
                            {isLoadingMore ? (
                                <div className="flex items-center gap-2 text-muted-foreground ">
                                    <Spinner className="w-4 h-4" />
                                    <span className="text-sm">Loading more…</span>
                                </div>
                            ) : hasMore && totalCount > 0 ? (
                                <span className="text-sm text-muted-foreground ">
                                    Showing {loadedCount} of {totalCount} segments
                                </span>
                            ) : null}
                        </div>
                    )}
                </>
            )}
            {editable && <div aria-hidden className="h-20" />}
            </div>
            </div>
        </ScrollArea>
    );
};
