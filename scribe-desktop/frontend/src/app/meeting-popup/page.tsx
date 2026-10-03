'use client'

import { invoke } from '@tauri-apps/api/core'
import { X } from 'lucide-react'
import { OverlayButton, OverlayCard } from '@/components/OverlayCard'

export default function MeetingPopupPage() {
  return (
    <OverlayCard
      eyebrow="Meeting detected"
      title="Start recording?"
      subtitle="Begin live transcription"
    >
      <OverlayButton
        variant="ghost"
        aria-label="Dismiss"
        className="w-8 px-0"
        onClick={() => invoke('meeting_popup_dismiss')}
      >
        <X className="h-3.5 w-3.5" />
      </OverlayButton>
      <OverlayButton variant="primary" onClick={() => invoke('meeting_popup_start_recording')}>
        Record
      </OverlayButton>
    </OverlayCard>
  )
}
