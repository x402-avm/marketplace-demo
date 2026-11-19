import React, { useEffect, useMemo, useRef, useState } from 'react'
import { PayButton, RawOutput, fileName, getFileUrl } from '../kit'
import type { ToolUIProps } from '../kit'
import { clock, readResult, videoIdFrom } from './parse'
import './yt_mcp.css'

export const domain = 'yt_mcp'

const TRANSCRIPT = 'get_yt_transcript'
const DOWNLOAD = 'download_yt_video'

interface Line {
  text: string
  start: number
  duration: number
}

const oneLine = (s: string) => s.replace(/\s*\n\s*/g, ' ').trim()

const CopyButton: React.FC<{ value: string; label: string; done?: string; className?: string }> = ({ value, label, done = 'Copied', className }) => {
  const [ok, setOk] = useState(false)
  const timer = useRef<number>()
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return (
    <button
      type="button"
      className={className ?? 'yt-btn yt-btn--small'}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value)
          setOk(true)
          window.clearTimeout(timer.current)
          timer.current = window.setTimeout(() => setOk(false), 1600)
        } catch {
          setOk(false)
        }
      }}
    >
      {ok ? done : label}
    </button>
  )
}

const Transcript: React.FC<{ lines: Line[] }> = ({ lines }) => {
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  const shown = useMemo(() => (needle ? lines.filter((l) => oneLine(l.text).toLowerCase().includes(needle)) : lines), [lines, needle])
  const all = lines.map((l) => `[${clock(l.start)}] ${oneLine(l.text)}`).join('\n')
  const last = lines.length ? lines[lines.length - 1] : null
  const span = last ? last.start + last.duration : 0
  const mark = (t: string) => {
    if (!needle) return t
    const i = t.toLowerCase().indexOf(needle)
    if (i < 0) return t
    return (
      <>
        {t.slice(0, i)}
        <mark>{t.slice(i, i + needle.length)}</mark>
        {t.slice(i + needle.length)}
      </>
    )
  }
  return (
    <div className="yt-tr" data-testid="yt-transcript">
      <div className="yt-tr__bar">
        <div className="yt-tr__find">
          <label htmlFor="yt-find" className="yt-label">
            Find in transcript
          </label>
          <input id="yt-find" type="search" className="yt-input" value={q} placeholder="Type a word" onChange={(e) => setQ(e.target.value)} />
        </div>
        <CopyButton value={all} label="Copy all with times" className="yt-btn" />
        <CopyButton value={lines.map((l) => oneLine(l.text)).join(' ')} label="Copy text only" className="yt-btn" />
      </div>
      <p className="yt-note" aria-live="polite">
        {needle ? `${shown.length} of ${lines.length} lines contain "${q.trim()}".` : `${lines.length} lines, ${clock(span)} of speech.`}
      </p>
      {shown.length === 0 ? (
        <p className="yt-empty">No line contains "{q.trim()}". Clear the search to see all lines.</p>
      ) : (
        <ol className="yt-lines">
          {shown.map((l, i) => (
            <li key={`${l.start}-${i}`} className="yt-line">
              <span className="yt-line__time">{clock(l.start)}</span>
              <p className="yt-line__text">{mark(oneLine(l.text))}</p>
              <CopyButton value={oneLine(l.text)} label="Copy" done="Copied" className="yt-line__copy" />
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

const YtDesk: React.FC<ToolUIProps> = (props) => {
  const { args, setArgs, running, result, resultTool, text, files, canRun, listing, tool } = props
  const mode = tool?.name === DOWNLOAD ? DOWNLOAD : TRANSCRIPT
  // Start on the cheaper transcript; the page selects the first tool in the list, which is the download.
  useEffect(() => {
    if (tool?.name === DOWNLOAD && !result && !running) props.selectTool(TRANSCRIPT)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // The link and format live here so they survive switching between the two actions.
  const [url, setUrlState] = useState<string>(typeof args.url === 'string' ? args.url : typeof args.video_id === 'string' ? args.video_id : '')
  const [format, setFormatState] = useState<string>(args.format === 'audio' ? 'audio' : 'video')
  const id = videoIdFrom(url)
  const touched = url.trim().length > 0

  const [ranFor, setRanFor] = useState<string | null>(null)

  const setUrl = (v: string) => {
    const vid = videoIdFrom(v)
    setUrlState(v)
    setArgs({ ...args, url: v, format, video_id: vid ?? v.trim() })
  }
  const setFormat = (f: string) => {
    setFormatState(f)
    setArgs({ ...args, url, format: f, video_id: id ?? url.trim() })
  }

  const priceT = props.priceOf(TRANSCRIPT)
  const priceD = props.priceOf(DOWNLOAD)
  const usesPass = props.payLabel.startsWith('Run with')
  const label = usesPass
    ? mode === TRANSCRIPT ? 'Get the transcript with your pass' : `Download the ${format} with your pass`
    : mode === TRANSCRIPT ? `Pay ${priceT} and get the transcript` : `Pay ${priceD} and download the ${format}`

  const go = () => {
    if (!id) return
    setRanFor(mode)
    const canonical = `https://www.youtube.com/watch?v=${id}`
    if (mode === TRANSCRIPT) props.run({ tool: TRANSCRIPT, args: { video_id: id } })
    else props.run({ tool: DOWNLOAD, args: { url: /^https?:\/\//i.test(url.trim()) ? url.trim() : canonical, format } })
  }

  const data = result && resultTool ? readResult(text) : null
  const showing = result && resultTool === (ranFor ?? resultTool) ? resultTool : null
  const failed = Boolean(result?.isError)
  const lines: Line[] | null =
    showing === TRANSCRIPT && !failed && data?.status === 'success' && Array.isArray(data.transcript)
      ? data.transcript.filter((l: any) => l && typeof l.text === 'string').map((l: any) => ({ text: l.text, start: Number(l.start) || 0, duration: Number(l.duration) || 0 }))
      : null
  const unavailable = showing === TRANSCRIPT && !failed && data && data.status !== 'success'
  const filePath: string | null =
    showing === DOWNLOAD && !failed ? (typeof data?.file === 'string' ? data.file : files.find((f) => /\.(mp4|webm|mkv|m4a|mp3|opus|ogg|wav)$/i.test(f)) ?? null) : null
  const isAudio = filePath ? /\.(m4a|mp3|opus|ogg|wav)$/i.test(filePath) : false

  const urlHint = !touched
    ? 'Paste a YouTube link. Watch, share, shorts and embed links all work.'
    : id
      ? ''
      : 'This does not look like a YouTube video link. It should look like youtube.com/watch?v=... or youtu.be/...'

  return (
    <div className="yt">
      <section className="yt-link" aria-labelledby="yt-link-h">
        <h2 id="yt-link-h" className="yt-h">
          Video link
        </h2>
        <input
          id="yt-url"
          className="yt-input yt-input--url"
          data-testid="field-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          aria-label="YouTube link"
          aria-invalid={touched && !id}
          aria-describedby="yt-url-hint"
          value={url}
          placeholder="https://www.youtube.com/watch?v=jNQXAC9IVRw"
          disabled={running}
          onChange={(e) => setUrl(e.target.value)}
        />
        <p id="yt-url-hint" className={`yt-note${touched && !id ? ' yt-note--bad' : ''}`} role={touched && !id ? 'alert' : undefined}>
          {urlHint || (
            <>
              Video id <code className="yt-id" data-testid="field-video_id">{id}</code>
            </>
          )}
        </p>
      </section>

      <fieldset className="yt-acts" disabled={running}>
        <legend className="yt-h">What do you want from it?</legend>
        <label className={`yt-act${mode === TRANSCRIPT ? ' is-on' : ''}`}>
          <input type="radio" name="yt-act" checked={mode === TRANSCRIPT} onChange={() => props.selectTool(TRANSCRIPT)} />
          <span className="yt-act__body">
            <span className="yt-act__name">Read the transcript</span>
            <span className="yt-act__what">The captions as timed lines you can search and copy. Nothing is saved to disk.</span>
            <span className="yt-act__price">{priceT}</span>
          </span>
        </label>
        <label className={`yt-act${mode === DOWNLOAD ? ' is-on' : ''}`}>
          <input type="radio" name="yt-act" checked={mode === DOWNLOAD} onChange={() => props.selectTool(DOWNLOAD)} />
          <span className="yt-act__body">
            <span className="yt-act__name">Download the file</span>
            <span className="yt-act__what">Saves the video or only its sound on the service, then plays it here. Longer videos take longer.</span>
            <span className="yt-act__price">{priceD}</span>
          </span>
        </label>
      </fieldset>

      {mode === DOWNLOAD && (
        <fieldset className="yt-format" data-testid="field-format" data-value={format} disabled={running}>
          <legend className="yt-label">Keep</legend>
          {(['video', 'audio'] as const).map((f) => (
            <label key={f} className={`yt-format__opt${format === f ? ' is-on' : ''}`}>
              <input type="radio" name="yt-format" value={f} checked={format === f} onChange={() => setFormat(f)} />
              <span>{f === 'video' ? 'Picture and sound' : 'Sound only'}</span>
            </label>
          ))}
        </fieldset>
      )}

      <div className="yt-go">
        <PayButton
          label={label}
          running={running}
          runningLabel={mode === TRANSCRIPT ? 'Fetching the transcript' : `Downloading the ${format}, this can take a minute`}
          disabled={!canRun || !id || listing.online === false}
          onClick={go}
        />
      </div>

      {(running || result) && (
        <section className="yt-out" aria-labelledby="yt-out-h" aria-busy={running}>
          <h2 id="yt-out-h" className="yt-h">
            {running ? (mode === TRANSCRIPT ? 'Fetching the transcript' : 'Downloading') : failed ? 'That did not work' : showing === DOWNLOAD ? 'Downloaded file' : 'Transcript'}
          </h2>
          {running && <p className="yt-note">The result appears here when YouTube has answered.</p>}
          {!running && failed && (
            <div className="yt-fail" role="alert">
              <p className="yt-fail__what">
                {resultTool === DOWNLOAD ? 'The video could not be downloaded.' : 'The transcript could not be fetched.'}
              </p>
              <p className="yt-fail__why">{text.replace(/^Error:\s*/, '')}</p>
            </div>
          )}
          {!running && unavailable && (
            <div className="yt-fail" role="alert">
              <p className="yt-fail__what">This video has no transcript to read.</p>
              <p className="yt-fail__why">{String(data?.error ?? 'YouTube did not return captions.').split('\n')[0]}</p>
            </div>
          )}
          {!running && lines && <Transcript lines={lines} />}
          {!running && filePath && (
            <figure className="yt-file" data-testid="yt-download">
              {isAudio ? (
                <audio className="yt-file__media" src={getFileUrl(filePath)} controls preload="metadata" />
              ) : (
                <video className="yt-file__media" src={getFileUrl(filePath)} controls preload="metadata" />
              )}
              <figcaption className="yt-file__cap">
                <span className="yt-file__title">{typeof data?.title === 'string' && data.title ? data.title : 'Downloaded'}</span>
                <span className="yt-file__name">{fileName(filePath)}</span>
                <a className="yt-btn yt-btn--small" href={getFileUrl(filePath)} download={fileName(filePath)}>
                  Save a copy
                </a>
              </figcaption>
            </figure>
          )}
          {!running && result && <RawOutput text={text} title="What the service said" />}
        </section>
      )}
    </div>
  )
}

export default YtDesk
