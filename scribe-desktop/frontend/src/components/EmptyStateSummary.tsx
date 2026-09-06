'use client';

import { FileQuestion, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from '@/components/ui/empty';

interface EmptyStateSummaryProps {
  onGenerate: () => void;
  hasModel: boolean;
  isGenerating?: boolean;
}

export function EmptyStateSummary({ onGenerate, hasModel, isGenerating = false }: EmptyStateSummaryProps) {
  return (
    <Empty className="h-full border-none">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <FileQuestion />
        </EmptyMedia>
        <EmptyTitle>No Summary Generated Yet</EmptyTitle>
        <EmptyDescription>
          Generate an AI-powered summary of your meeting transcript to get key points, action items, and decisions.
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <Button
                  onClick={onGenerate}
                  disabled={!hasModel || isGenerating}
                  className="gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  {isGenerating ? 'Generating...' : 'Generate Summary'}
                </Button>
              </div>
            </TooltipTrigger>
            {!hasModel && (
              <TooltipContent>
                <p>Please select a model in Settings first</p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>

        {!hasModel && (
          <p className="text-xs text-warning">
            Please select a model in Settings first
          </p>
        )}
      </EmptyContent>
    </Empty>
  );
}
