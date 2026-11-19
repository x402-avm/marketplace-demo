import React, { useEffect, useRef, useState } from 'react'
import { PayButton, RawOutput, UploadButton, getFileUrl, fileName } from '../kit'
import type { ToolUIProps } from '../kit'
import './image_edit_mcp.css'

export const domain = 'image_edit_mcp'

type Mode = 'resize_image' | 'compress_image'

interface Source {
  path: string
  name: string
  url: string
  bytes: number | null
  width: number
  height: number
}

interface Outcome {
  tool: Mode
  path: string
  url: string
  bytes: number | null
  width: number
  height: number
  quality?: number
}

function formatBytes(n: number | null): string {
  if (n === null) return 'unknown'
  if (n < 1024) return `${n} bytes`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

function measure(url: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight })
    img.onerror = () => reject(new Error('The image could not be read.'))
    img.src = url
  })
}

async function fetchBytes(url: string): Promise<number | null> {
  try {
    const res = await fetch(url)
    if (!res.ok) return null
    return (await res.blob()).size
  } catch {
    return null
  }
}

function qualityNote(q: number): string {
  if (q >= 85) return 'Looks the same as the original; the file shrinks a little.'
  if (q >= 60) return 'A good balance. Most people will not see a difference.'
  if (q >= 35) return 'Noticeably smaller. Fine detail and smooth skies start to blur.'
  return 'As small as it gets. Expect visible blocks and banding.'
}

const ImageEditStudio: React.FC<ToolUIProps> = ({ run, running, result, resultTool, text, priceOf, payLabel, canRun, listing }) => {
  const [mode, setMode] = useState<Mode>('resize_image')
  const [source, setSource] = useState<Source | null>(null)
  const [pathInput, setPathInput] = useState('')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [width, setWidth] = useState(0)
  const [height, setHeight] = useState(0)
  const [locked, setLocked] = useState(true)
  const [quality, setQuality] = useState(60)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const pending = useRef<{ tool: Mode; quality?: number; source: Source } | null>(null)
  const seen = useRef<unknown>(null)

  const usePass = payLabel.startsWith('Run with')

  const loadSource = async (path: string, name: string, bytes: number | null, localUrl?: string) => {
    setLoadError(null)
    const url = localUrl ?? getFileUrl(path)
    try {
      const dims = await measure(url)
      const size = bytes ?? (await fetchBytes(getFileUrl(path)))
      setSource({ path, name, url, bytes: size, ...dims })
      setWidth(Math.max(1, Math.round(dims.width / 2)))
      setHeight(Math.max(1, Math.round(dims.height / 2)))
      setOutcome(null)
    } catch (e: any) {
      setSource(null)
      setLoadError(`${name} could not be opened as an image. Choose a JPEG, PNG or WebP file.`)
    }
  }

  // When a call finishes, measure what came back.
  useEffect(() => {
    if (!result || result === seen.current) return
    seen.current = result
    const job = pending.current
    if (result.isError || !job || (resultTool !== 'resize_image' && resultTool !== 'compress_image')) return
    const path = text.trim().split('\n').find((l) => l.trim().startsWith('/'))?.trim()
    if (!path) return
    const url = getFileUrl(path)
    let alive = true
    Promise.all([measure(url).catch(() => ({ width: 0, height: 0 })), fetchBytes(url)]).then(([dims, bytes]) => {
      if (!alive) return
      setOutcome({ tool: job.tool, path, url, bytes, quality: job.quality, ...dims })
    })
    return () => {
      alive = false
    }
  }, [result, resultTool, text])

  const ratio = source ? source.width / source.height : 1
  const changeWidth = (w: number) => {
    setWidth(w)
    if (locked && source && w > 0) setHeight(Math.max(1, Math.round(w / ratio)))
  }
  const changeHeight = (h: number) => {
    setHeight(h)
    if (locked && source && h > 0) setWidth(Math.max(1, Math.round(h * ratio)))
  }
  const scaleTo = (f: number) => {
    if (!source) return
    setWidth(Math.max(1, Math.round(source.width * f)))
    setHeight(Math.max(1, Math.round(source.height * f)))
  }

  const sizeValid = width >= 1 && height >= 1 && width <= 8000 && height <= 8000
  const price = priceOf(mode)
  const pay = usePass ? 'with your pass' : `pay ${price}`
  const label =
    mode === 'resize_image'
      ? `Resize to ${width || '?'} by ${height || '?'}, ${pay}`
      : `Compress at quality ${quality}, ${pay}`

  const start = () => {
    if (!source) return
    pending.current = { tool: mode, quality: mode === 'compress_image' ? quality : undefined, source }
    setOutcome(null)
    const args = mode === 'resize_image' ? { image_path: source.path, width, height } : { image_path: source.path, quality }
    run({ tool: mode, args })
  }

  const failed = result?.isError && (resultTool === 'resize_image' || resultTool === 'compress_image')
  const before = pending.current?.source ?? source

  return (
    <div className="imgedit">
      <div className="imgedit__source">
        <div className="imgedit__pick">
          <h2 className="svc__h2 imgedit__h">Your image</h2>
          <UploadButton
            accept="image/png,image/jpeg,image/webp"
            label={source ? 'Choose a different image' : 'Choose an image'}
            testid="upload-image"
            onPath={(path, file) => {
              setPathInput(path)
              loadSource(path, file.name, file.size, URL.createObjectURL(file))
            }}
          />
        </div>

        {source ? (
          <figure className="imgedit__orig">
            <img src={source.url} alt={`The image you chose, ${source.name}`} />
            <figcaption>
              <span className="imgedit__name">{source.name}</span>
              <span className="imgedit__dims">
                {source.width} by {source.height} pixels, {formatBytes(source.bytes)}
              </span>
            </figcaption>
          </figure>
        ) : (
          <p className="imgedit__empty">Choose a JPEG, PNG or WebP from your computer. You will see it here with its size before you pay for anything.</p>
        )}
        {loadError && (
          <p className="imgedit__error" role="alert">
            {loadError}
          </p>
        )}

        <details className="imgedit__path">
          <summary>Use a file already on the server</summary>
          <div className="imgedit__pathrow">
            <label className="visually-hidden" htmlFor="imgedit-path">
              Server path of the image
            </label>
            <input
              id="imgedit-path"
              className="input"
              data-testid="field-image_path"
              value={pathInput}
              placeholder="/path/to/image.jpg"
              onChange={(e) => setPathInput(e.target.value)}
            />
            <button
              type="button"
              className="imgedit__btn"
              disabled={!pathInput.trim()}
              onClick={() => loadSource(pathInput.trim(), fileName(pathInput.trim()), null)}
            >
              Open it
            </button>
          </div>
        </details>
      </div>

      <div className="imgedit__work">
        <div className="imgedit__modes" role="radiogroup" aria-label="What to do with the image">
          {(
            [
              ['resize_image', 'Resize', 'Change its width and height'],
              ['compress_image', 'Compress', 'Make the file smaller'],
            ] as const
          ).map(([m, name, hint]) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={mode === m}
              className={`imgedit__mode${mode === m ? ' is-on' : ''}`}
              data-testid={`mode-${m}`}
              onClick={() => setMode(m)}
            >
              <span className="imgedit__modename">{name}</span>
              <span className="imgedit__modehint">
                {hint}, {priceOf(m)}
              </span>
            </button>
          ))}
        </div>

        {mode === 'resize_image' ? (
          <fieldset className="imgedit__resize" disabled={running}>
            <legend className="visually-hidden">New size in pixels</legend>
            <div className="imgedit__dimrow">
              <div className="imgedit__dim">
                <label htmlFor="imgedit-w">Width</label>
                <input
                  id="imgedit-w"
                  className="input"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={8000}
                  data-testid="field-width"
                  value={width || ''}
                  onChange={(e) => changeWidth(Number(e.target.value))}
                />
              </div>
              <button
                type="button"
                className={`imgedit__lock${locked ? ' is-on' : ''}`}
                aria-pressed={locked}
                data-testid="lock-aspect"
                onClick={() => setLocked(!locked)}
                title={locked ? 'Width and height change together' : 'Width and height change separately'}
              >
                <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                  {locked ? (
                    <path d="M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5z" fill="none" stroke="currentColor" strokeWidth="2" />
                  ) : (
                    <path d="M7 11V8a5 5 0 0 1 9.6-2M5 11h14v10H5z" fill="none" stroke="currentColor" strokeWidth="2" />
                  )}
                </svg>
                <span>{locked ? 'Proportions kept' : 'Proportions free'}</span>
              </button>
              <div className="imgedit__dim">
                <label htmlFor="imgedit-h">Height</label>
                <input
                  id="imgedit-h"
                  className="input"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={8000}
                  data-testid="field-height"
                  value={height || ''}
                  onChange={(e) => changeHeight(Number(e.target.value))}
                />
              </div>
            </div>
            {source && (
              <div className="imgedit__scales" aria-label="Quick sizes">
                {[0.25, 0.5, 0.75, 2].map((f) => (
                  <button key={f} type="button" className="imgedit__chip" onClick={() => scaleTo(f)}>
                    {f * 100}%
                  </button>
                ))}
                <span className="imgedit__orighint">
                  Original {source.width} by {source.height}
                </span>
              </div>
            )}
            {!sizeValid && <p className="imgedit__hint">Width and height must be between 1 and 8000 pixels.</p>}
          </fieldset>
        ) : (
          <fieldset className="imgedit__compress" disabled={running}>
            <legend className="visually-hidden">Compression quality</legend>
            <div className="imgedit__qhead">
              <label htmlFor="imgedit-q">Quality</label>
              <output htmlFor="imgedit-q" className="imgedit__qval">
                {quality}
              </output>
            </div>
            <input
              id="imgedit-q"
              className="imgedit__range"
              type="range"
              min={5}
              max={95}
              step={5}
              data-testid="field-quality"
              value={quality}
              onChange={(e) => setQuality(Number(e.target.value))}
            />
            <div className="imgedit__qends" aria-hidden="true">
              <span>Smallest file</span>
              <span>Best looking</span>
            </div>
            <p className="imgedit__hint">{qualityNote(quality)} The result is saved as a JPEG.</p>
          </fieldset>
        )}

        <div className="imgedit__go">
          <PayButton
            label={label}
            running={running}
            runningLabel={mode === 'resize_image' ? 'Resizing your image' : 'Compressing your image'}
            disabled={!canRun || !source || listing.online === false || (mode === 'resize_image' && !sizeValid)}
            onClick={start}
          />
          {!source && <p className="imgedit__hint">Choose an image first.</p>}
        </div>
      </div>

      <section className="imgedit__result" aria-live="polite" aria-labelledby="imgedit-result-h">
        <h2 id="imgedit-result-h" className="svc__h2 imgedit__h">
          Before and after
        </h2>
        {running && <p className="imgedit__empty">Working on it. You pay only if the image comes back.</p>}
        {!running && !result && <p className="imgedit__empty">Run a resize or compression to compare the result with your original here.</p>}
        {failed && (
          <p className="imgedit__error" role="alert">
            The service could not {resultTool === 'resize_image' ? 'resize' : 'compress'} this image. It said: {text || 'nothing'}
          </p>
        )}
        {outcome && before && !running && (
          <>
            {outcome.tool === 'compress_image' ? (
              <Compare before={before.url} after={outcome.url} />
            ) : (
              <SideBySide before={before} after={outcome} />
            )}
            <Ledger before={before} after={outcome} />
            <p className="imgedit__download">
              <a href={outcome.url} download={fileName(outcome.path)} target="_blank" rel="noopener noreferrer">
                Open the {outcome.tool === 'resize_image' ? 'resized' : 'compressed'} image
              </a>
            </p>
          </>
        )}
        {result && !running && <RawOutput text={text} title="What the service sent back" />}
      </section>
    </div>
  )
}

/** Overlaid comparison with a draggable divider; the range input underneath makes it keyboard accessible. */
const Compare: React.FC<{ before: string; after: string }> = ({ before, after }) => {
  const [pos, setPos] = useState(50)
  const box = useRef<HTMLDivElement>(null)
  const drag = (clientX: number) => {
    const r = box.current?.getBoundingClientRect()
    if (!r) return
    setPos(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)))
  }
  return (
    <div className="imgedit__compare">
      <div
        ref={box}
        className="imgedit__stage"
        style={{ ['--pos' as any]: `${pos}%` }}
        onPointerDown={(e) => {
          ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
          drag(e.clientX)
        }}
        onPointerMove={(e) => e.buttons === 1 && drag(e.clientX)}
      >
        <img src={after} alt="After compression" className="imgedit__layer" draggable={false} />
        <img src={before} alt="Before compression" className="imgedit__layer imgedit__layer--before" draggable={false} />
        <span className="imgedit__divider" aria-hidden="true" />
        <span className="imgedit__tag imgedit__tag--l" aria-hidden="true">
          Before
        </span>
        <span className="imgedit__tag imgedit__tag--r" aria-hidden="true">
          After
        </span>
      </div>
      <label className="visually-hidden" htmlFor="imgedit-divider">
        Divider position, before on the left and after on the right
      </label>
      <input
        id="imgedit-divider"
        className="imgedit__range"
        type="range"
        min={0}
        max={100}
        value={Math.round(pos)}
        onChange={(e) => setPos(Number(e.target.value))}
      />
      <p className="imgedit__hint">Drag across the picture, or use the slider, to compare. Zoomed in, compression shows in edges and flat colour.</p>
    </div>
  )
}

/** Resized result drawn at its true size relative to the original, so the change in pixels is visible. */
const SideBySide: React.FC<{ before: Source; after: Outcome }> = ({ before, after }) => {
  const biggest = Math.max(before.width, after.width || 1)
  return (
    <div className="imgedit__pair">
      <figure>
        <div className="imgedit__frame">
          <img src={before.url} alt="Original" style={{ width: `${(before.width / biggest) * 100}%` }} />
        </div>
        <figcaption>Before, {before.width} by {before.height}</figcaption>
      </figure>
      <figure>
        <div className="imgedit__frame">
          <img src={after.url} alt="Resized" style={{ width: `${((after.width || 1) / biggest) * 100}%` }} />
        </div>
        <figcaption>After, {after.width} by {after.height}</figcaption>
      </figure>
    </div>
  )
}

const Ledger: React.FC<{ before: Source; after: Outcome }> = ({ before, after }) => {
  const saved = before.bytes !== null && after.bytes !== null ? before.bytes - after.bytes : null
  const pct = saved !== null && before.bytes ? Math.round((saved / before.bytes) * 100) : null
  const pxBefore = before.width * before.height
  const pxAfter = after.width * after.height
  return (
    <table className="imgedit__ledger" data-testid="imgedit-ledger">
      <caption className="visually-hidden">Size before and after</caption>
      <thead>
        <tr>
          <th scope="col">
            <span className="visually-hidden">Measure</span>
          </th>
          <th scope="col">Before</th>
          <th scope="col">After</th>
          <th scope="col">Change</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">Pixels</th>
          <td>
            {before.width} by {before.height}
          </td>
          <td>
            {after.width} by {after.height}
          </td>
          <td>{pxBefore === pxAfter ? 'Same' : `${pxAfter > pxBefore ? '+' : ''}${Math.round(((pxAfter - pxBefore) / pxBefore) * 100)}% pixels`}</td>
        </tr>
        <tr>
          <th scope="row">File size</th>
          <td>{formatBytes(before.bytes)}</td>
          <td>{formatBytes(after.bytes)}</td>
          <td className="imgedit__saving">
            {saved === null ? 'Unknown' : saved >= 0 ? `${formatBytes(saved)} smaller (${pct}%)` : `${formatBytes(-saved)} larger (+${-(pct ?? 0)}%)`}
          </td>
        </tr>
      </tbody>
    </table>
  )
}

export default ImageEditStudio
