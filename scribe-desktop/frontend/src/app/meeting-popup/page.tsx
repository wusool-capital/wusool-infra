'use client'

import { invoke } from '@tauri-apps/api/core'
import { Mic, X } from 'lucide-react'

export default function MeetingPopupPage() {
  const startRecording = () => invoke('meeting_popup_start_recording')
  const dismiss = () => invoke('meeting_popup_dismiss')

  return (
    <div className="group relative w-screen h-screen">
      <div
        onClick={startRecording}
        className="flex h-full items-center gap-3 rounded-2xl border border-white/10 bg-[#1c1c1f]/95 px-3 backdrop-blur-xl cursor-pointer transition-colors hover:bg-[#242428]/95"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-gradient-to-br from-indigo-400 to-indigo-600 shadow-sm">
          <Mic className="h-4.5 w-4.5 text-white" strokeWidth={2.25} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-indigo-300/90">
            Meeting Detected
          </p>
          <p className="text-[13px] font-semibold leading-tight text-white">
            Start recording?
          </p>
          <p className="text-[11px] leading-tight text-white/55">
            Click to begin transcription
          </p>
        </div>
      </div>

      <button
        onClick={(e) => {
          e.stopPropagation()
          dismiss()
        }}
        aria-label="Dismiss"
        className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-white/70 opacity-0 transition-opacity hover:bg-white/20 hover:text-white group-hover:opacity-100"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  )
}
