'use client'

import Image from 'next/image'
import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'

interface OverlayCardProps {
  eyebrow: string
  title: string
  subtitle?: string
  /** 0-1 fill of the thin bar along the bottom edge; omit for no bar. */
  progress?: number
  children: ReactNode
}

/** Shared look for Scribe's small always-on-top notifications. */
export function OverlayCard({ eyebrow, title, subtitle, progress, children }: OverlayCardProps) {
  const [shown, setShown] = useState(false)
  useEffect(() => setShown(true), [])

  return (
    <div
      className={`relative h-screen w-screen overflow-hidden rounded-[18px] border border-white/[0.09] bg-gradient-to-b from-[#1e1e24] to-[#131316] shadow-[inset_0_1px_0_rgba(255,255,255,0.07)] transition duration-200 ease-out motion-reduce:transition-none ${
        shown ? 'translate-y-0 opacity-100' : '-translate-y-1 opacity-0'
      }`}
    >
      {/* Soft brand-colour glow behind the logo */}
      <div
        aria-hidden
        className="pointer-events-none absolute -left-8 -top-10 h-28 w-28 rounded-full bg-indigo-500/20 blur-2xl"
      />

      <div className="relative flex h-full items-center gap-3 px-3.5">
        <div className="h-10 w-10 shrink-0 overflow-hidden rounded-[11px] shadow-[0_2px_8px_rgba(0,0,0,0.5)] ring-1 ring-white/15">
          <Image src="/logo-collapsed.png" alt="WusoolScribe" width={40} height={40} priority />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-indigo-300">
            {eyebrow}
          </p>
          <p className="truncate text-[13.5px] font-semibold leading-tight tracking-tight text-white tabular-nums">
            {title}
          </p>
          {subtitle && (
            <p className="truncate text-[11px] leading-tight text-white/60">{subtitle}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">{children}</div>
      </div>

      {progress !== undefined && (
        <div
          aria-hidden
          className="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-indigo-500 to-indigo-300"
          style={{ width: `${Math.min(1, Math.max(0, progress)) * 100}%` }}
        />
      )}
    </div>
  )
}

type Variant = 'primary' | 'danger' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-gradient-to-b from-indigo-400 to-indigo-600 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25)] hover:from-indigo-300 hover:to-indigo-500',
  danger:
    'bg-gradient-to-b from-red-400 to-red-600 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25)] hover:from-red-300 hover:to-red-500',
  ghost: 'bg-white/[0.08] text-white/85 hover:bg-white/[0.16] hover:text-white',
}

interface OverlayButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onClick'> {
  variant: Variant
  onClick: () => unknown
}

// The overlay closes the moment its action runs, so hold the pressed look
// briefly or the click would give no visible feedback at all.
const PRESS_FEEDBACK_MS = 140

export function OverlayButton({
  variant,
  onClick,
  className = '',
  children,
  ...props
}: OverlayButtonProps) {
  const [pressed, setPressed] = useState(false)

  const handleClick = async () => {
    if (pressed) return
    setPressed(true)
    await new Promise((resolve) => setTimeout(resolve, PRESS_FEEDBACK_MS))
    try {
      await onClick()
    } finally {
      setPressed(false)
    }
  }

  return (
    <button
      {...props}
      onClick={handleClick}
      disabled={pressed}
      className={`flex h-8 cursor-pointer items-center justify-center rounded-lg px-3 text-[11.5px] font-semibold outline-none transition duration-100 hover:brightness-110 active:scale-[0.95] focus-visible:ring-2 focus-visible:ring-white/70 motion-reduce:transition-none motion-reduce:active:scale-100 ${
        pressed ? 'scale-[0.95] brightness-90 motion-reduce:scale-100' : ''
      } ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  )
}
