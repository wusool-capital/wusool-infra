'use client';

import { motion } from 'framer-motion';
import { useRecordingState } from '@/contexts/RecordingStateContext';
import { useEffect, useState } from 'react';
import { formatElapsed } from '@/lib/formatElapsed';

interface RecordingStatusBarProps {
  isPaused?: boolean;
}

export const RecordingStatusBar: React.FC<RecordingStatusBarProps> = ({ isPaused = false }) => {
  // Get recording duration from backend-synced context (in seconds)
  // Backend polls every 500ms, providing smooth updates
  const { activeDuration, isRecording } = useRecordingState();

  // Display state synced from backend
  const [displaySeconds, setDisplaySeconds] = useState(0);

  // Sync with backend duration when it changes (handles refresh/navigation)
  useEffect(() => {
    if (activeDuration !== null) {
      // Round to nearest second to avoid decimal issues
      setDisplaySeconds(Math.floor(activeDuration));
    }
  }, [activeDuration]);

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg"
    >
      <div className={`w-2 h-2 rounded-full ${isPaused ? 'bg-warning' : 'bg-destructive motion-safe:animate-pulse'}`} />
      <span className={`text-sm ${isPaused ? 'text-warning' : 'text-foreground/90'}`}>
        {isPaused ? 'Paused' : 'Recording'}
      </span>
      <span className="text-sm text-muted-foreground tabular-nums">{formatElapsed(displaySeconds)}</span>
    </motion.div>
  );
};
