"use client";

import { Button } from '@/components/ui/button';
import { Merge, Trash2, X } from 'lucide-react';
import type { TranscriptEditorApi } from '@/hooks/meeting-details/useTranscriptEditor';

export function TranscriptSelectionBar({ editor }: { editor: TranscriptEditorApi }) {
  const count = editor.selectedIds.size;
  if (count === 0) return null;

  return (
    <div className="absolute bottom-6 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 shadow-lg">
      <span className="mr-2 text-sm">
        {count} {count === 1 ? 'line' : 'lines'} selected
      </span>
      <Button size="sm" variant="ghost" onClick={editor.selectAll}>
        Select all
      </Button>
      {count > 1 && (
        <Button size="sm" variant="ghost" onClick={() => void editor.mergeSelected()}>
          <Merge size={14} />
          Merge
        </Button>
      )}
      <Button
        size="sm"
        variant="ghost"
        className="text-destructive hover:text-destructive"
        onClick={() => void editor.deleteSelected()}
      >
        <Trash2 size={14} />
        Delete
      </Button>
      <Button size="icon" variant="ghost" className="h-8 w-8" title="Clear selection (Esc)" onClick={editor.clearSelection}>
        <X size={14} />
      </Button>
    </div>
  );
}
