'use client'

import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { MicOff } from 'lucide-react'

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

  if (!countdown) return null

  const secondsLeft = Math.ceil(remainingMs / 1000)
  const progress = Math.min(1, remainingMs / (countdown.duration_secs * 1000))
  const focusRing =
    'outline-none focus-visible:ring-2 focus-visible:ring-white/60 active:scale-[0.97] motion-reduce:active:scale-100'

  return (
    <div className="relative h-screen w-screen overflow-hidden rounded-2xl border border-white/10 bg-[#1c1c1f]">
      <div className="flex h-full items-center gap-3 px-3.5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-gradient-to-br from-indigo-400 to-indigo-600 shadow-sm">
          <MicOff className="h-[18px] w-[18px] text-white" strokeWidth={2.25} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-indigo-300/90">
            Meeting ended
          </p>
          <p className="truncate text-[13px] font-semibold leading-tight text-white">
            {countdown.auto_stop ? `Stopping in ${secondsLeft}s` : 'Stop recording?'}
          </p>
        </div>

        <button
          onClick={() => invoke('recording_pill_keep_recording')}
          className={`rounded-lg bg-white/10 px-2.5 py-1.5 text-[11px] font-medium text-white/85 transition hover:bg-white/20 hover:text-white ${focusRing}`}
        >
          Keep
        </button>
        <button
          onClick={() => invoke('recording_pill_stop')}
          className={`rounded-lg bg-red-500 px-2.5 py-1.5 text-[11px] font-semibold text-white transition hover:bg-red-400 ${focusRing}`}
        >
          Stop now
        </button>
      </div>

      <div
        className="absolute bottom-0 left-0 h-[3px] bg-indigo-400/80"
        style={{ width: `${progress * 100}%` }}
        aria-hidden
      />
    </div>
  )
}
