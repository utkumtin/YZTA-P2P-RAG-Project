import { useRef, useState, useEffect } from 'react'
import type { SummarizeOption } from '../../types/summarize'

const SUMMARIZE_OPTIONS: SummarizeOption[] = [
  { id: 'short',  label: 'Kısa',    hint: 'Anahtar noktaları koruyarak kısa özet', maxLength: 200 },
  { id: 'normal', label: 'Dengeli',  hint: 'Önemli detaylarla birlikte dengeli bir özet',          maxLength: 500 },
  { id: 'long',   label: 'Detaylı', hint: 'Bölüm bölüm, örnekleri ve nüansları içeren tam özet', maxLength: 1000 },
]

interface SummaryButtonProps {
  disabled: boolean
  onSummarize: (option: SummarizeOption) => void
}

export default function SummaryButton({ disabled, onSummarize }: SummaryButtonProps) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [hover, setHover] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) {
      setMounted(true)
    } else if (mounted) {
      const t = setTimeout(() => setMounted(false), 180)
      return () => clearTimeout(t)
    }
  }, [open, mounted])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => !disabled && setOpen(o => !o)}
        disabled={disabled}
        style={{
          appearance: 'none', cursor: disabled ? 'default' : 'pointer', width: '100%',
          background: open ? 'var(--accent-softer)' : 'transparent',
          border: '1px solid ' + (open ? 'var(--accent-border-soft)' : 'var(--b-08)'),
          borderRadius: 8, padding: '10px 12px',
          display: 'flex', alignItems: 'center', gap: 10,
          color: disabled ? 'var(--txt-4)' : '#fff',
          opacity: disabled ? 0.5 : 1,
          transition: 'background .15s ease, border-color .15s ease',
        }}
      >
        <span style={{
          width: 26, height: 26, borderRadius: 6, flexShrink: 0,
          background: 'var(--accent-soft)', color: 'var(--accent-fg)',
          display: 'grid', placeItems: 'center',
        }}>
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M3 4h10M3 8h10M3 12h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        </span>
        <span style={{ flex: 1, textAlign: 'left', fontSize: 13, letterSpacing: '-.005em' }}>Özet</span>
        <svg
          width="10" height="10" viewBox="0 0 10 10" fill="none"
          style={{
            color: 'var(--txt-3)',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform .22s cubic-bezier(.4,0,.2,1)',
          }}
        >
          <path d="M2 4l3 3 3-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {mounted && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, zIndex: 20,
          background: 'var(--panel)',
          border: '1px solid var(--b-10)',
          borderRadius: open ? 14 : 22,
          padding: 6,
          boxShadow: open
            ? '0 18px 40px rgba(0,0,0,.45), 0 2px 6px rgba(0,0,0,.3)'
            : '0 4px 14px rgba(0,0,0,.3)',
          transformOrigin: 'top center',
          opacity: open ? 1 : 0,
          transform: open
            ? 'translateY(0) scaleX(1) scaleY(1)'
            : 'translateY(-10px) scaleX(.55) scaleY(.4)',
          transition: open
            ? 'opacity .22s ease, transform .42s cubic-bezier(.34,1.56,.5,1), border-radius .42s cubic-bezier(.34,1.56,.5,1)'
            : 'opacity .18s ease, transform .32s cubic-bezier(.5,0,.75,0), border-radius .32s cubic-bezier(.5,0,.75,0)',
          pointerEvents: open ? 'auto' : 'none',
          willChange: 'transform, opacity',
          overflow: 'hidden',
        }}>
          {SUMMARIZE_OPTIONS.map((opt, i) => (
            <button
              key={opt.id}
              onMouseEnter={() => setHover(opt.id)}
              onMouseLeave={() => setHover(null)}
              onClick={() => { setOpen(false); onSummarize(opt) }}
              style={{
                appearance: 'none', cursor: 'pointer', width: '100%',
                background: hover === opt.id ? 'var(--accent-softer)' : 'transparent',
                border: 'none', borderRadius: 7,
                padding: '9px 10px', textAlign: 'left',
                display: 'block', color: '#fff',
                opacity: open ? 1 : 0,
                transform: open ? 'translateY(0)' : 'translateY(-6px)',
                transition: open
                  ? `opacity .26s ease ${80 + i * 55}ms, transform .34s cubic-bezier(.34,1.4,.5,1) ${80 + i * 55}ms, background .12s ease`
                  : 'opacity .12s ease, transform .18s ease, background .12s ease',
              }}
            >
              <div style={{
                fontSize: 13, fontWeight: 500, letterSpacing: '-.005em',
                color: hover === opt.id ? 'var(--accent-fg)' : '#fff',
                transition: 'color .15s ease',
              }}>
                {opt.label}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--txt-3)', marginTop: 3, lineHeight: 1.4, letterSpacing: '-.003em' }}>
                {opt.hint}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
