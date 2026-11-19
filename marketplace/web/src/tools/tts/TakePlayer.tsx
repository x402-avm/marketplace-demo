import React, { useCallback, useEffect, useRef, useState } from 'react'

const BUCKETS = 720

export function clock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) sec = 0
  const m = Math.floor(sec / 60)
  const s = sec - m * 60
  return `${m}:${s < 10 ? '0' : ''}${s.toFixed(1)}`
}

/** Peak amplitude per bucket, read from the real audio. */
async function decodePeaks(url: string): Promise<{ peaks: Float32Array; duration: number }> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`The recording could not be loaded (HTTP ${res.status}).`)
  const buf = await res.arrayBuffer()
  // An offline context decodes without asking the browser for permission to play.
  const ctx = new OfflineAudioContext(1, 1, 44100)
  const audio = await ctx.decodeAudioData(buf)
  const data = audio.getChannelData(0)
  const step = Math.max(1, Math.floor(data.length / BUCKETS))
  const peaks = new Float32Array(Math.ceil(data.length / step))
  let max = 0
  for (let i = 0; i < peaks.length; i++) {
    let p = 0
    const end = Math.min(data.length, (i + 1) * step)
    for (let j = i * step; j < end; j++) {
      const v = Math.abs(data[j])
      if (v > p) p = v
    }
    peaks[i] = p
    if (p > max) max = p
  }
  if (max > 0) for (let i = 0; i < peaks.length; i++) peaks[i] /= max
  return { peaks, duration: audio.duration }
}

interface Props {
  url: string
  fileName: string
  /** shown to screen readers and on the play button */
  label: string
  onDuration?: (sec: number) => void
  large?: boolean
}

/** A recorded take: its waveform drawn from the decoded audio, play and pause, seeking, and a download link. */
export const TakePlayer: React.FC<Props> = ({ url, fileName, label, onDuration, large }) => {
  const audioRef = useRef<HTMLAudioElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [peaks, setPeaks] = useState<Float32Array | null>(null)
  const [duration, setDuration] = useState(0)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const onDurationRef = useRef(onDuration)
  onDurationRef.current = onDuration

  useEffect(() => {
    let alive = true
    setPeaks(null)
    setError(null)
    decodePeaks(url)
      .then(({ peaks, duration }) => {
        if (!alive) return
        setPeaks(peaks)
        setDuration(duration)
        onDurationRef.current?.(duration)
      })
      .catch((e) => alive && setError(String(e.message || e)))
    return () => {
      alive = false
    }
  }, [url])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    const w = wrap.clientWidth
    const h = wrap.clientHeight
    if (!w || !h) return
    const dpr = window.devicePixelRatio || 1
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
    }
    const g = canvas.getContext('2d')
    if (!g) return
    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.clearRect(0, 0, w, h)
    const ink = getComputedStyle(canvas).color
    const mid = h / 2
    const bar = 2
    const gap = 1
    const count = Math.floor(w / (bar + gap))
    const progress = duration ? time / duration : 0
    g.fillStyle = ink
    if (!peaks) {
      g.globalAlpha = 0.25
      g.fillRect(0, mid - 0.5, w, 1)
      g.globalAlpha = 1
      return
    }
    for (let i = 0; i < count; i++) {
      const from = Math.floor((i / count) * peaks.length)
      const to = Math.max(from + 1, Math.floor(((i + 1) / count) * peaks.length))
      let p = 0
      for (let j = from; j < to; j++) if (peaks[j] > p) p = peaks[j]
      const half = Math.max(0.75, p * (mid - 2))
      g.globalAlpha = i / count < progress ? 1 : 0.32
      g.fillRect(i * (bar + gap), mid - half, bar, half * 2)
    }
    g.globalAlpha = 1
    if (progress > 0) {
      g.fillRect(Math.min(w - 1.5, progress * w), 0, 1.5, h)
    }
  }, [peaks, duration, time])

  useEffect(draw, [draw])

  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => draw())
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [draw])

  // Smooth playhead while playing.
  useEffect(() => {
    if (!playing) return
    let raf = 0
    const tick = () => {
      const a = audioRef.current
      if (a) setTime(a.currentTime)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing])

  const toggle = () => {
    const a = audioRef.current
    if (!a) return
    if (a.paused) {
      // only one take plays at a time, so takes can be compared one after another
      document.querySelectorAll<HTMLAudioElement>('audio.tts-take__audio').forEach((other) => {
        if (other !== a) other.pause()
      })
      a.play().catch((e) => setError(String(e.message || e)))
    } else {
      a.pause()
    }
  }

  const seek = (sec: number) => {
    const a = audioRef.current
    if (!a || !duration) return
    const t = Math.min(duration, Math.max(0, sec))
    a.currentTime = t
    setTime(t)
  }

  const onPointer = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.type === 'pointermove' && e.buttons !== 1) return
    const r = e.currentTarget.getBoundingClientRect()
    seek(((e.clientX - r.left) / r.width) * duration)
  }

  const onKey = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 5 : 1
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') seek(time + step)
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') seek(time - step)
    else if (e.key === 'Home') seek(0)
    else if (e.key === 'End') seek(duration)
    else if (e.key === ' ' || e.key === 'Enter') toggle()
    else return
    e.preventDefault()
  }

  return (
    <div className={`tts-take__player${large ? ' tts-take__player--large' : ''}`}>
      <audio
        ref={audioRef}
        className="tts-take__audio"
        src={url}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => {
          setPlaying(false)
          if (audioRef.current) setTime(audioRef.current.currentTime)
        }}
        onEnded={() => {
          setPlaying(false)
          setTime(0)
        }}
      />
      <button type="button" className="tts-take__play" onClick={toggle} aria-label={`${playing ? 'Pause' : 'Play'} ${label}`}>
        <svg viewBox="0 0 20 20" aria-hidden="true" width="18" height="18">
          {playing ? <path d="M5 3h3.5v14H5zM11.5 3H15v14h-3.5z" fill="currentColor" /> : <path d="M5 2.5v15l12.5-7.5z" fill="currentColor" />}
        </svg>
      </button>
      <div
        ref={wrapRef}
        className="tts-take__wave"
        role="slider"
        tabIndex={0}
        aria-label={`Position in ${label}`}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration * 10) / 10}
        aria-valuenow={Math.round(time * 10) / 10}
        aria-valuetext={`${clock(time)} of ${clock(duration)}`}
        onPointerDown={onPointer}
        onPointerMove={onPointer}
        onKeyDown={onKey}
      >
        <canvas ref={canvasRef} className="tts-take__canvas" aria-hidden="true" />
      </div>
      <p className="tts-take__time">
        {error ? (
          <span className="tts-take__err">{error}</span>
        ) : (
          <>
            <span>{clock(time)}</span>
            <span className="tts-take__of"> / {peaks ? clock(duration) : 'loading'}</span>
          </>
        )}
      </p>
      <a className="tts-take__dl" href={url} download={fileName}>
        Download WAV
      </a>
    </div>
  )
}
