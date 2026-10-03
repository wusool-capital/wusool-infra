'use client'

import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { OverlayButton, OverlayCard } from '@/components/OverlayCard'

interface MeetingEndCountdown {
  ends_at_ms: number
  duration_secs: number
  auto_stop: boolean
}

export default function MeetingEndedPage() {
  const [countdown, setCountdown] = useState<MeetingEndCountdown | null>(null)
  const [remainingMs, setRemainingMs] = useState(0)

  // Events can fire before this window's webview is ready, so also pull the
  // current countdown on mount.
  useEffect(() => {
    invoke<MeetingEndCountdown | null>('recording_pill_state')
      .then(setCountdown)
      .catch((error) => console.error('[MeetingEnded] failed to read countdown:', error))

    const unlistenStart = listen<MeetingEndCountdown>('meeting-end-countdown', (e) =>
      setCountdown(e.payload)
    )
    const unlistenClear = listen('meeting-end-countdown-cleared', () => setCountdown(null))
    return () => {
      unlistenStart.then((fn) => fn())
      unlistenClear.then((fn) => fn())
    }
  }, [])

  useEffect(() => {
    if (!countdown) return
    const tick = () => setRemainingMs(Math.max(0, countdown.ends_at_ms - Date.now()))
    tick()
    const id = setInterval(tick, 100)
    return () => clearInterval(id)
  }, [countdown])

  // Render the card straight away so it paints even if scripts are throttled
  // while the app is inactive; the countdown fills in once it loads.
  const autoStop = countdown?.auto_stop ?? true
  const secondsLeft = Math.ceil(remainingMs / 1000)
  const progress = countdown ? remainingMs / (countdown.duration_secs * 1000) : 1

  return (
    <OverlayCard
      eyebrow="Meeting ended"
      title={!countdown ? 'Stopping soon' : autoStop ? `Stopping in ${secondsLeft}s` : 'Stop recording?'}
      subtitle={autoStop ? 'Your transcript will be saved' : 'The call has ended'}
      progress={progress}
    >
      <OverlayButton variant="ghost" onClick={() => invoke('recording_pill_keep_recording')}>
        Keep
      </OverlayButton>
      <OverlayButton variant="danger" onClick={() => invoke('recording_pill_stop')}>
        Stop now
      </OverlayButton>
    </OverlayCard>
  )
}
