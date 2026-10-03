'use client'

import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { Pause, Play, Square } from 'lucide-react'

interface RecordingState {
  is_paused: boolean
  active_duration: number | null
}

interface MeetingEndCountdown {
  ends_at_ms: number
  auto_stop: boolean
}

function formatElapsed(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(sec).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

export default function RecordingPillPage() {
  const [paused, setPaused] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [countdown, setCountdown] = useState<MeetingEndCountdown | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)

  useEffect(() => {
    const poll = async () => {
      try {
        const state = await invoke<RecordingState>('get_recording_state')
        setPaused(state.is_paused)
        setElapsed(state.active_duration ?? 0)
      } catch (error) {
        console.error('[RecordingPill] failed to read recording state:', error)
      }
    }
    poll()
    const id = setInterval(poll, 1000)
    return () => clearInterval(id)
  }, [])

  // Events can fire before this window's webview is ready, so also pull the
  // current countdown on mount.
  useEffect(() => {
    invoke<MeetingEndCountdown | null>('recording_pill_state')
      .then(setCountdown)
      .catch((error) => console.error('[RecordingPill] failed to read countdown:', error))

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
    const tick = () =>
      setSecondsLeft(Math.max(0, Math.ceil((countdown.ends_at_ms - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [countdown])

  const stop = () => invoke('recording_pill_stop')
  const keepRecording = () => invoke('recording_pill_keep_recording')
  const togglePause = () => invoke(paused ? 'resume_recording' : 'pause_recording')

  const shell =
    'flex h-full items-center gap-3 rounded-2xl border border-white/10 bg-[#1c1c1f]/95 px-3 backdrop-blur-xl'

  if (countdown) {
    return (
      <div className={shell}>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-300/90">
            Meeting ended
          </p>
          <p className="text-[13px] font-semibold leading-tight text-white">
            {countdown.auto_stop ? `Stopping in ${secondsLeft}s` : 'Stop recording?'}
          </p>
        </div>
        <button
          onClick={keepRecording}
          className="rounded-lg bg-white/10 px-2.5 py-1.5 text-[11px] font-medium text-white/80 hover:bg-white/20 hover:text-white"
        >
          Keep recording
        </button>
        <button
          onClick={stop}
          className="rounded-lg bg-red-500 px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-red-400"
        >
          Stop now
        </button>
      </div>
    )
  }

  return (
    <div className={shell}>
      <span
        className={`h-2.5 w-2.5 shrink-0 rounded-full ${
          paused ? 'bg-amber-400' : 'animate-pulse bg-red-500'
        }`}
      />
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-white/55">
          {paused ? 'Paused' : 'Recording'}
        </p>
        <p className="font-mono text-[15px] font-semibold leading-tight text-white">
          {formatElapsed(elapsed)}
        </p>
      </div>
      <button
        onClick={togglePause}
        aria-label={paused ? 'Resume recording' : 'Pause recording'}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
      >
        {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
      </button>
      <button
        onClick={stop}
        aria-label="Stop recording"
        className="flex h-8 w-8 items-center justify-center rounded-full bg-red-500 text-white hover:bg-red-400"
      >
        <Square className="h-3.5 w-3.5 fill-current" />
      </button>
    </div>
  )
}
