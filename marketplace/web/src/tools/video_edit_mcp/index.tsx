import React, { useEffect, useRef, useState } from 'react'
import { PayButton, RawOutput, UploadButton, fileName, getFileUrl } from '../kit'
import type { ToolUIProps } from '../kit'
import './video_edit_mcp.css'

export const domain = 'video_edit_mcp'

const TOOL = 'trim_video'
const FRAMES = 10

const round1 = (n: number) => Math.round(n * 10) / 10

function stamp(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) sec = 0
  const m = Math.floor(sec / 60)
  const s = sec - m * 60
  return `${m}:${s < 10 ? '0' : ''}${s.toFixed(1)}`
}

function secs(n: number): string {
  return `${n.toFixed(1)} s`
}

/** Grab evenly spaced still frames from the video so the timeline shows what is where. */
function useFilmstrip(url: string | null, duration: number): string[] {
  const [frames, setFrames] = useState<string[]>([])
  useEffect(() => {
    setFrames([])
    if (!url || !duration) return
    let alive = true
    const v = document.createElement('video')
    v.muted = true
    v.preload = 'auto'
    v.src = url
    const canvas = document.createElement('canvas')
    const out: string[] = []
    const grab = (i: number) => {
      if (!alive || i >= FRAMES) return
      const t = Math.min(duration - 0.05, ((i + 0.5) / FRAMES) * duration)
      const onSeek = () => {
        v.removeEventListener('seeked', onSeek)
        if (!alive) return
        const w = 160
        const h = Math.round((w * (v.videoHeight || 9)) / (v.videoWidth || 16))
        canvas.width = w
        canvas.height = h
        const g = canvas.getContext('2d')
        if (!g) return
        try {
          g.drawImage(v, 0, 0, w, h)
          out.push(canvas.toDataURL('image/jpeg', 0.6))
          setFrames([...out])
        } catch {
          return
        }
        grab(i + 1)
      }
      v.addEventListener('seeked', onSeek)
      v.currentTime = t
    }
    const start = () => grab(0)
    v.addEventListener('loadeddata', start, { once: true })
    return () => {
      alive = false
      v.removeAttribute('src')
      v.load()
    }
  }, [url, duration])
  return frames
}

interface HandleProps {
  which: 'start' | 'end'
  value: number
  min: number
  max: number
  duration: number
  onChange: (v: number) => void
  trackRef: React.RefObject<HTMLDivElement>
  disabled: boolean
}

const Handle: React.FC<HandleProps> = ({ which, value, min, max, duration, onChange, trackRef, disabled }) => {
  const clamp = (v: number) => round1(Math.min(max, Math.max(min, v)))
  const fromPointer = (e: React.PointerEvent) => {
    const r = trackRef.current?.getBoundingClientRect()
    if (!r) return
    onChange(clamp(((e.clientX - r.left) / r.width) * duration))
  }
  return (
    <div
      className={`vtrim-handle vtrim-handle--${which}`}
      style={{ left: `${(value / duration) * 100}%` }}
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled || undefined}
      aria-label={which === 'start' ? 'Clip start' : 'Clip end'}
      aria-valuemin={round1(min)}
      aria-valuemax={round1(max)}
      aria-valuenow={value}
      aria-valuetext={`${value.toFixed(1)} seconds`}
      onPointerDown={(e) => {
        if (disabled) return
        e.currentTarget.setPointerCapture(e.pointerId)
        e.stopPropagation()
      }}
      onPointerMove={(e) => {
        if (!disabled && e.currentTarget.hasPointerCapture(e.pointerId)) fromPointer(e)
      }}
      onKeyDown={(e) => {
        if (disabled) return
        const step = e.shiftKey ? 1 : 0.1
        if (e.key === 'ArrowRight' || e.key === 'ArrowUp') onChange(clamp(value + step))
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') onChange(clamp(value - step))
        else if (e.key === 'Home') onChange(clamp(min))
        else if (e.key === 'End') onChange(clamp(max))
        else return
        e.preventDefault()
      }}
    >
      <span className="vtrim-handle__grip" aria-hidden="true" />
    </div>
  )
}

const Player: React.FC<{ path: string; title: string; onDuration?: (d: number) => void; testid?: string }> = ({ path, title, onDuration, testid }) => {
  const [dur, setDur] = useState<number | null>(null)
  const [bad, setBad] = useState(false)
  const url = getFileUrl(path)
  return (
    <figure className="vtrim-out__fig" data-testid={testid}>
      <figcaption className="vtrim-out__cap">
        <span className="vtrim-out__title">{title}</span>
        <span className="vtrim-out__dur">{bad ? 'cannot be played here' : dur === null ? 'measuring' : secs(dur)}</span>
      </figcaption>
      <video
        className="vtrim-out__video"
        src={url}
        controls
        preload="metadata"
        onLoadedMetadata={(e) => {
          const d = e.currentTarget.duration
          setDur(d)
          onDuration?.(d)
        }}
        onError={() => setBad(true)}
      />
      <p className="vtrim-out__file">
        <span className="vtrim-out__name">{fileName(path)}</span>
        <a href={url} download={fileName(path)}>
          Download
        </a>
      </p>
    </figure>
  )
}

const TrimBench: React.FC<ToolUIProps> = (props) => {
  const { args, setArgs, running, result, resultTool, text, files, canRun, listing } = props
  const argsRef = useRef(args)
  argsRef.current = args
  const update = (patch: Record<string, any>) => setArgs({ ...argsRef.current, ...patch })

  const path: string = typeof args.video_path === 'string' ? args.video_path : ''
  const start: number = typeof args.start_sec === 'number' ? args.start_sec : 0
  const end: number = typeof args.end_sec === 'number' ? args.end_sec : 5

  const [pathDraft, setPathDraft] = useState(path)
  const [duration, setDuration] = useState(0)
  const [previewError, setPreviewError] = useState(false)
  const [playhead, setPlayhead] = useState(0)
  const [uploadedName, setUploadedName] = useState<string | null>(null)
  const [source, setSource] = useState<{ path: string; duration: number } | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const trackRef = useRef<HTMLDivElement>(null)
  const stopAt = useRef<number | null>(null)

  useEffect(() => setPathDraft(path), [path])

  const url = path ? getFileUrl(path) : null
  const frames = useFilmstrip(previewError ? null : url, duration)
  const known = duration > 0

  const choose = (p: string) => {
    setDuration(0)
    setPreviewError(false)
    setPlayhead(0)
    update({ video_path: p, start_sec: 0, end_sec: 5 })
  }

  const onMeta = (d: number) => {
    setDuration(d)
    const a = argsRef.current
    const s = typeof a.start_sec === 'number' ? a.start_sec : 0
    const e = typeof a.end_sec === 'number' ? a.end_sec : 5
    if (e > d || s >= d) update({ start_sec: Math.min(s, round1(Math.max(0, d - 0.1))), end_sec: round1(Math.min(e, d)) })
    else if (typeof a.end_sec !== 'number') update({ start_sec: s, end_sec: round1(Math.min(5, d)) })
  }

  const length = round1(end - start)
  const problem = !path
    ? 'Choose a video first.'
    : start < 0
      ? 'The start cannot be before the beginning of the video.'
      : end <= start
        ? 'The end has to come after the start.'
        : known && end > duration + 0.05
          ? `The video is only ${secs(duration)} long. Move the end back.`
          : null

  const playSelection = () => {
    const v = videoRef.current
    if (!v) return
    v.currentTime = start
    stopAt.current = end
    v.play().catch(() => undefined)
  }

  const cut = () => {
    setSource({ path, duration })
    props.run({ tool: TOOL, args: { video_path: path, start_sec: start, end_sec: end } })
  }

  const usesPass = props.payLabel.startsWith('Run with')
  const label = usesPass ? `Cut the ${secs(Math.max(0, length))} clip with your pass` : `Pay ${props.priceOf(TOOL)} and cut the ${secs(Math.max(0, length))} clip`

  const outPath = result && !result.isError && resultTool === TOOL ? files.find((f) => /\.(mp4|webm|mov)$/i.test(f)) ?? null : null
  const failed = result?.isError && resultTool === TOOL
  const original = source

  const pct = (v: number) => `${known ? (v / duration) * 100 : 0}%`

  return (
    <div className="vtrim">
      <section className="vtrim-source" aria-labelledby="vtrim-source-h">
        <h2 id="vtrim-source-h" className="vtrim-h">
          Video
        </h2>
        <div className="vtrim-source__row">
          <UploadButton
            accept="video/*"
            label={path ? 'Upload a different video' : 'Upload a video'}
            testid="upload-video"
            onPath={(p, f) => {
              setUploadedName(f.name)
              choose(p)
            }}
          />
          <form
            className="vtrim-source__path"
            onSubmit={(e) => {
              e.preventDefault()
              if (pathDraft.trim() && pathDraft.trim() !== path) {
                setUploadedName(null)
                choose(pathDraft.trim())
              }
            }}
          >
            <label htmlFor="vtrim-path" className="vtrim-label">
              or a file already on the service
            </label>
            <div className="vtrim-source__pathrow">
              <input
                id="vtrim-path"
                className="vtrim-input"
                data-testid="field-video_path"
                value={pathDraft}
                placeholder="/path/to/video.mp4"
                spellCheck={false}
                onChange={(e) => setPathDraft(e.target.value)}
                onBlur={() => {
                  if (pathDraft.trim() !== path) {
                    setUploadedName(null)
                    choose(pathDraft.trim())
                  }
                }}
              />
              <button type="submit" className="vtrim-btn">
                Load
              </button>
            </div>
          </form>
        </div>
        {path && uploadedName && <p className="vtrim-note">Uploaded {uploadedName}.</p>}
      </section>

      {path && (
        <section className="vtrim-bench" aria-labelledby="vtrim-bench-h">
          <h2 id="vtrim-bench-h" className="vtrim-h vtrim-visually-hidden">
            Choose the part to keep
          </h2>
          {!previewError ? (
            <video
              ref={videoRef}
              key={url ?? ''}
              className="vtrim-preview"
              src={url ?? undefined}
              controls
              preload="auto"
              onLoadedMetadata={(e) => onMeta(e.currentTarget.duration)}
              onError={() => setPreviewError(true)}
              onTimeUpdate={(e) => {
                const t = e.currentTarget.currentTime
                setPlayhead(t)
                if (stopAt.current !== null && t >= stopAt.current) {
                  e.currentTarget.pause()
                  stopAt.current = null
                }
              }}
              onPause={() => (stopAt.current = null)}
            />
          ) : (
            <p className="vtrim-note vtrim-note--box">
              This file cannot be previewed in the browser, so there is no timeline. Type the start and end below; the service can still cut it.
            </p>
          )}

          {known && (
            <div className="vtrim-timeline">
              <div
                className="vtrim-track"
                ref={trackRef}
                onPointerDown={(e) => {
                  const r = e.currentTarget.getBoundingClientRect()
                  const t = ((e.clientX - r.left) / r.width) * duration
                  if (videoRef.current) videoRef.current.currentTime = t
                  setPlayhead(t)
                }}
              >
                <div className="vtrim-strip" aria-hidden="true">
                  {Array.from({ length: FRAMES }, (_, i) =>
                    frames[i] ? <img key={i} src={frames[i]} alt="" draggable={false} /> : <span key={i} className="vtrim-strip__blank" />,
                  )}
                </div>
                <div className="vtrim-shade" style={{ left: 0, width: pct(start) }} aria-hidden="true" />
                <div className="vtrim-shade" style={{ left: pct(end), right: 0 }} aria-hidden="true" />
                <div className="vtrim-keep" style={{ left: pct(start), width: pct(Math.max(0, end - start)) }} aria-hidden="true" />
                <div className="vtrim-playhead" style={{ left: pct(playhead) }} aria-hidden="true" />
                <Handle
                  which="start"
                  value={start}
                  min={0}
                  max={Math.max(0, end - 0.1)}
                  duration={duration}
                  trackRef={trackRef}
                  disabled={running}
                  onChange={(v) => update({ start_sec: v })}
                />
                <Handle
                  which="end"
                  value={Math.min(end, duration)}
                  min={start + 0.1}
                  max={round1(duration)}
                  duration={duration}
                  trackRef={trackRef}
                  disabled={running}
                  onChange={(v) => update({ end_sec: v })}
                />
              </div>
              <div className="vtrim-scale" aria-hidden="true">
                <span>0:00.0</span>
                <span>{stamp(duration / 2)}</span>
                <span>{stamp(duration)}</span>
              </div>
            </div>
          )}

          <div className="vtrim-controls">
            <div className="vtrim-time">
              <label htmlFor="vtrim-start" className="vtrim-label">
                Start, in seconds
              </label>
              <input
                id="vtrim-start"
                className="vtrim-input vtrim-input--num"
                data-testid="field-start_sec"
                type="number"
                min={0}
                step={0.1}
                max={known ? round1(duration) : undefined}
                value={Number.isFinite(start) ? start : ''}
                disabled={running}
                onChange={(e) => update({ start_sec: e.target.value === '' ? 0 : Number(e.target.value) })}
              />
              {known && !previewError && (
                <button type="button" className="vtrim-btn vtrim-btn--small" disabled={running} onClick={() => update({ start_sec: Math.min(round1(playhead), round1(end - 0.1)) })}>
                  Start at {stamp(playhead)}
                </button>
              )}
            </div>
            <div className="vtrim-time">
              <label htmlFor="vtrim-end" className="vtrim-label">
                End, in seconds
              </label>
              <input
                id="vtrim-end"
                className="vtrim-input vtrim-input--num"
                data-testid="field-end_sec"
                type="number"
                min={0}
                step={0.1}
                max={known ? round1(duration) : undefined}
                value={Number.isFinite(end) ? end : ''}
                disabled={running}
                onChange={(e) => update({ end_sec: e.target.value === '' ? 0 : Number(e.target.value) })}
              />
              {known && !previewError && (
                <button type="button" className="vtrim-btn vtrim-btn--small" disabled={running} onClick={() => update({ end_sec: Math.max(round1(playhead), round1(start + 0.1)) })}>
                  End at {stamp(playhead)}
                </button>
              )}
            </div>
            <div className="vtrim-sum" aria-live="polite">
              <p className="vtrim-sum__len">{length > 0 ? secs(length) : 'No clip'}</p>
              <p className="vtrim-sum__detail">
                {length > 0 ? `kept from ${stamp(start)} to ${stamp(end)}` : 'Set an end after the start'}
                {known ? ` of ${secs(duration)}` : ''}
              </p>
              {known && !previewError && length > 0 && (
                <button type="button" className="vtrim-btn vtrim-btn--small" onClick={playSelection}>
                  Play only this part
                </button>
              )}
            </div>
          </div>
        </section>
      )}

      <div className="vtrim-go">
        {problem && path && <p className="vtrim-problem">{problem}</p>}
        {!path && <p className="vtrim-note">Upload a video, then drag the two handles on the timeline to the part you want to keep.</p>}
        <PayButton
          label={label}
          running={running}
          runningLabel={`Cutting ${secs(Math.max(0, length))} from the video`}
          disabled={!canRun || Boolean(problem) || listing.online === false}
          onClick={cut}
        />
        <p className="vtrim-note">The price is the same for any length. You pay only if the clip is made.</p>
      </div>

      {(running || result) && (
        <section className="vtrim-out" aria-labelledby="vtrim-out-h" aria-busy={running}>
          <h2 id="vtrim-out-h" className="vtrim-h">
            {running ? 'Cutting the clip' : failed ? 'The clip was not made' : 'Your clip'}
          </h2>
          {running && <p className="vtrim-note">The service re-encodes the part you chose. Short clips take a few seconds.</p>}
          {failed && (
            <div className="vtrim-fail" role="alert">
              <p className="vtrim-fail__what">
                {/not allowed|403/i.test(text)
                  ? 'The service is not allowed to open that file. Upload the video instead of typing a path.'
                  : /not found|404|exist/i.test(text)
                    ? 'The service could not find that file. Check the path or upload the video.'
                    : /start|end/i.test(text)
                      ? 'The start and end times were not accepted. The end has to come after the start.'
                      : 'The video could not be cut.'}
              </p>
            </div>
          )}
          {outPath && (
            <div className="vtrim-out__pair">
              {original && <Player path={original.path} title="Original" />}
              <Player path={outPath} title="Trimmed clip" testid="vtrim-result" />
            </div>
          )}
          {outPath && (
            <button type="button" className="vtrim-btn" onClick={() => { setUploadedName(null); choose(outPath) }}>
              Trim this clip again
            </button>
          )}
          {result && <RawOutput text={text} title="What the service said" />}
        </section>
      )}
    </div>
  )
}

export default TrimBench
