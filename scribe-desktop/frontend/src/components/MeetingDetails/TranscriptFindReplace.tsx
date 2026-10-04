"use client";

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { TranscriptEditorApi } from '@/hooks/meeting-details/useTranscriptEditor';

const COUNT_DEBOUNCE_MS = 250;

export function TranscriptFindReplace({ editor }: { editor: TranscriptEditorApi }) {
  const { findOpen, setFindOpen, findMatches, replaceAll } = editor;
  const [find, setFind] = useState('');
  const [replacement, setReplacement] = useState('');
  const [matchCount, setMatchCount] = useState(0);
  const [isReplacing, setIsReplacing] = useState(false);

  // Counts matches across the whole meeting, including pages not scrolled to yet.
  useEffect(() => {
    if (!findOpen || find === '') {
      setMatchCount(0);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await findMatches(find);
        if (!cancelled) setMatchCount(result.match_count);
      } catch (error) {
        console.error('Find failed:', error);
      }
    }, COUNT_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [find, findOpen, findMatches]);

  const handleReplace = async () => {
    setIsReplacing(true);
    try {
      const changed = await replaceAll(find, replacement);
      if (changed !== undefined) {
        toast.success(`Updated ${changed} ${changed === 1 ? 'line' : 'lines'}`);
        setMatchCount(0);
        setFind('');
      }
    } finally {
      setIsReplacing(false);
    }
  };

  return (
    <Popover open={findOpen} onOpenChange={setFindOpen}>
      <PopoverTrigger asChild>
        <Button size="sm" variant="outline" title="Find & replace (Cmd+F)">
          <Search size={16} />
          <span className="hidden xl:inline">Find</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 space-y-2">
        <Input
          autoFocus
          placeholder="Find"
          value={find}
          onChange={(e) => setFind(e.target.value)}
        />
        <Input
          placeholder="Replace with"
          value={replacement}
          onChange={(e) => setReplacement(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && matchCount > 0 && !isReplacing) void handleReplace();
          }}
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {find === '' ? 'Case-insensitive, whole transcript' : `${matchCount} ${matchCount === 1 ? 'match' : 'matches'}`}
          </span>
          <Button size="sm" disabled={matchCount === 0 || isReplacing} onClick={handleReplace}>
            Replace all
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
