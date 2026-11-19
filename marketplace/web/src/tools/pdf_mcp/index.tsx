import React, { useEffect, useId, useMemo, useRef, useState } from 'react'
import { PayButton, RawOutput, UploadButton, fileName } from '../kit'
import type { ToolUIProps } from '../kit'
import { payloads } from './pyrepr'
import './pdf_mcp.css'

export const domain = 'pdf_mcp'

const READ = 'pdf_read_all'
const FIND = 'pdf_search'

type Mode = 'read' | 'find'

interface ReadData {
  full_text: string
  page_count: number
  start_page: number
  total_pages: number
  truncated?: boolean
  next_page?: number | null
  hidden_text_detected?: boolean
}

interface Hit {
  page: number
  excerpt: string
  score?: number
  low_confidence?: boolean
}

interface FindData {
  query: string
  matches: Hit[]
  total_matches: number
  page_match_counts?: Record<string, number>
  searched_pages?: number
  hidden_text_detected?: boolean
}

interface Sheet {
  from: number
  to: number
  text: string
}

/** The service joins pages and paragraphs with the same blank lines, so pages can only be told apart when the counts agree. */
function sheetsOf(d: ReadData): Sheet[] {
  const text = d.full_text.replace(/\s+$/, '')
  const first = d.start_page || 1
  const count = Math.max(1, d.page_count || 1)
  if (count === 1) return [{ from: first, to: first, text }]
  const blocks = text.split(/\n{3,}/)
  if (blocks.length === count) return blocks.map((b, i) => ({ from: first + i, to: first + i, text: b }))
  return [{ from: first, to: first + count - 1, text }]
}

function paragraphs(text: string): string[] {
  return text
    .split(/\n\s*\n+/)
    .map((p) => p.replace(/\s*\n\s*/g, ' ').trim())
    .filter(Boolean)
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const STOP = new Set(['the', 'and', 'for', 'with', 'that', 'this', 'from', 'are', 'was', 'were', 'what', 'which', 'how', 'does', 'into'])

/** The phrase itself plus its longer words, longest first, so the best match wins. */
function termsOf(q: string): string[] {
  const phrase = q.trim()
  if (!phrase) return []
  const words = phrase
    .split(/\s+/)
    .map((w) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ''))
    .filter((w) => w.length > 2 && !STOP.has(w.toLowerCase()))
  return Array.from(new Set([phrase, ...words])).sort((a, b) => b.length - a.length)
}

const Marked: React.FC<{ text: string; terms: string[] }> = ({ text, terms }) => {
  if (!terms.length) return <>{text}</>
  const re = new RegExp(`(${terms.map(escapeRe).join('|')})`, 'giu')
  const parts = text.split(re)
  return (
    <>
      {parts.map((p, i) => (i % 2 === 1 ? <mark key={i} className="pdfm-mark">{p}</mark> : <React.Fragment key={i}>{p}</React.Fragment>))}
    </>
  )
}

const CopyButton: React.FC<{ text: string; label: string; done?: string }> = ({ text, label, done = 'Copied' }) => {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const t = window.setTimeout(() => setCopied(false), 1800)
    return () => window.clearTimeout(t)
  }, [copied])
  return (
    <button
      type="button"
      className="pdfm-copy"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(true)
        } catch {
          setCopied(false)
        }
      }}
    >
      <span aria-live="polite">{copied ? done : label}</span>
    </button>
  )
}

function jump(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' })
  el.focus({ preventScroll: true })
}

const pageLabel = (s: Sheet) => (s.from === s.to ? `Page ${s.from}` : `Pages ${s.from} to ${s.to}`)

const Reader: React.FC<{ data: ReadData; name: string }> = ({ data, name }) => {
  const base = useId().replace(/:/g, '')
  const sheets = useMemo(() => sheetsOf(data), [data])
  const [find, setFind] = useState('')
  const terms = useMemo(() => termsOf(find), [find])
  const merged = sheets.length === 1 && sheets[0].from !== sheets[0].to
  const total = data.total_pages || data.page_count
  const shown = sheets[sheets.length - 1]?.to ?? 0

  return (
    <div className="pdfm-reader">
      <header className="pdfm-reader__head">
        <div>
          <h3 className="pdfm-reader__title">{name}</h3>
          <p className="pdfm-reader__meta">
            {total === 1 ? 'One page' : `${total} pages`}
            {shown < total ? `, pages ${sheets[0].from} to ${shown} shown` : ''}
          </p>
        </div>
        <CopyButton text={data.full_text} label="Copy all text" />
      </header>

      <div className="pdfm-tools">
        <label className="pdfm-tools__label" htmlFor={`${base}-hl`}>
          Highlight words in this text
        </label>
        <input
          id={`${base}-hl`}
          className="input pdfm-tools__input"
          type="search"
          value={find}
          placeholder="Free, nothing is sent"
          onChange={(e) => setFind(e.target.value)}
        />
      </div>

      {merged && (
        <p className="pdfm-note">
          These pages arrived as one piece of text without page breaks, so they are shown together.
        </p>
      )}
      {data.hidden_text_detected && (
        <p className="pdfm-note">This PDF contains text that is hidden when printed. It is included below; read it with care.</p>
      )}

      <div className={`pdfm-reader__body${sheets.length > 1 ? ' has-rail' : ''}`}>
        {sheets.length > 1 && (
          <nav className="pdfm-rail" aria-label="Pages">
            <ol>
              {sheets.map((s) => (
                <li key={s.from}>
                  <button type="button" onClick={() => jump(`${base}-p${s.from}`)} aria-label={`Go to page ${s.from}`}>
                    {s.from}
                  </button>
                </li>
              ))}
            </ol>
          </nav>
        )}
        <div className="pdfm-sheets">
          {sheets.map((s) => (
            <article key={s.from} className="pdfm-sheet" aria-labelledby={`${base}-p${s.from}`}>
              <header className="pdfm-sheet__head">
                <h4 id={`${base}-p${s.from}`} tabIndex={-1} className="pdfm-sheet__folio">
                  {pageLabel(s)}
                </h4>
                <CopyButton text={s.text} label={s.from === s.to ? `Copy page ${s.from}` : 'Copy these pages'} />
              </header>
              <div className="pdfm-sheet__text">
                {paragraphs(s.text).map((p, i) => (
                  <p key={i}>
                    <Marked text={p} terms={terms} />
                  </p>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>

      {data.next_page ? (
        <p className="pdfm-note">
          The text is long, so the service stopped before page {data.next_page}. Pages {data.next_page} to {total} are not shown.
        </p>
      ) : null}
    </div>
  )
}

const Finds: React.FC<{ data: FindData; name: string }> = ({ data, name }) => {
  const base = useId().replace(/:/g, '')
  const terms = useMemo(() => termsOf(data.query), [data.query])
  const groups = useMemo(() => {
    const m = new Map<number, Hit[]>()
    for (const h of [...data.matches].sort((a, b) => a.page - b.page || (b.score ?? 0) - (a.score ?? 0))) {
      m.set(h.page, [...(m.get(h.page) ?? []), h])
    }
    return Array.from(m.entries())
  }, [data.matches])
  const pages = data.searched_pages ?? Math.max(0, ...data.matches.map((h) => h.page))
  const counts = data.page_match_counts ?? {}

  if (!data.matches.length) {
    return (
      <div className="pdfm-finds">
        <h3 className="pdfm-reader__title">No passages found</h3>
        <p className="pdfm-reader__meta">
          Nothing in {name} matched “{data.query}”. Try fewer words, or a word the document itself would use.
        </p>
      </div>
    )
  }

  return (
    <div className="pdfm-finds">
      <header className="pdfm-reader__head">
        <div>
          <h3 className="pdfm-reader__title">
            {data.matches.length === 1 ? 'One passage' : `${data.matches.length} passages`} for “{data.query}”
          </h3>
          <p className="pdfm-reader__meta">
            In {name}, {pages === 1 ? 'one page' : `${pages} pages`} searched
          </p>
        </div>
      </header>

      {pages > 1 && (
        <nav className="pdfm-strip" aria-label="Pages with passages">
          <ol>
            {Array.from({ length: pages }, (_, i) => i + 1).map((p) => {
              const n = counts[String(p)] ?? groups.find(([g]) => g === p)?.[1].length ?? 0
              return (
                <li key={p}>
                  <button
                    type="button"
                    className={n ? 'has-hits' : ''}
                    disabled={!n}
                    onClick={() => jump(`${base}-g${p}`)}
                    aria-label={n ? `Page ${p}, ${n} passage${n === 1 ? '' : 's'}` : `Page ${p}, no passages`}
                  >
                    <span className="pdfm-strip__page">{p}</span>
                    <span className="pdfm-strip__count" aria-hidden="true">
                      {n || ''}
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        </nav>
      )}

      {groups.map(([page, hits]) => (
        <section key={page} className="pdfm-group" aria-labelledby={`${base}-g${page}`}>
          <h4 id={`${base}-g${page}`} tabIndex={-1} className="pdfm-sheet__folio">
            Page {page}
          </h4>
          <ul className="pdfm-hits">
            {hits.map((h, i) => (
              <li key={i} className={`pdfm-hit${h.low_confidence ? ' is-weak' : ''}`}>
                <blockquote className="pdfm-hit__quote">
                  <Marked text={h.excerpt.replace(/\s*\n\s*/g, ' ').trim()} terms={terms} />
                </blockquote>
                <div className="pdfm-hit__foot">
                  {h.low_confidence && <span className="pdfm-hit__weak">Loose match, related in meaning only</span>}
                  <CopyButton text={`${h.excerpt.trim()}\n(${name}, page ${page})`} label="Copy with page" />
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

const PdfReaderUI: React.FC<ToolUIProps> = (props) => {
  const { running, result, resultTool, text, canRun, priceOf, payLabel } = props
  const uid = useId()
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [mode, setMode] = useState<Mode>('read')
  const [query, setQuery] = useState('')
  const asked = useRef<{ name: string }>({ name: '' })

  const withPass = payLabel.startsWith('Run with')
  const docName = name || (path ? fileName(path) : '')
  const tool = mode === 'read' ? READ : FIND
  const action = mode === 'read' ? 'read the whole document' : query.trim() ? `find “${query.trim()}”` : 'find these words'
  const label = withPass ? `${action[0].toUpperCase()}${action.slice(1)} with your pass` : `Pay ${priceOf(tool)} and ${action}`

  const go = () => {
    asked.current = { name: docName }
    const args = mode === 'read' ? { path: path.trim() } : { path: path.trim(), query: query.trim() }
    props.run({ tool, args })
  }

  const data = useMemo(() => (result && !result.isError ? payloads(text)[0] ?? null : null), [result, text])
  const shownName = asked.current.name || docName || 'this PDF'

  return (
    <div className="pdfm">
      <section className="pdfm-open" aria-labelledby={`${uid}-open`}>
        <h2 id={`${uid}-open`} className="svc__h2">
          Open a PDF
        </h2>
        <div className="pdfm-open__row">
          <UploadButton
            accept="application/pdf,.pdf"
            label={path ? 'Choose another PDF' : 'Choose a PDF'}
            testid="pdfm-upload"
            onPath={(p, f) => {
              setPath(p)
              setName(f.name)
            }}
          />
          {docName && (
            <p className="pdfm-open__doc">
              <span className="pdfm-open__name">{docName}</span> is open
            </p>
          )}
        </div>
        <div className="pdfm-open__path">
          <label className="field__label" htmlFor={`${uid}-path`}>
            Or the file’s path on the service
          </label>
          <input
            id={`${uid}-path`}
            className="input"
            data-testid="field-path"
            value={path}
            placeholder="/path/to/report.pdf"
            spellCheck={false}
            onChange={(e) => {
              setPath(e.target.value)
              setName('')
            }}
          />
        </div>

        <fieldset className="pdfm-mode">
          <legend className="field__label">What to do with it</legend>
          <div className="pdfm-mode__opts">
            <label className={`pdfm-mode__opt${mode === 'read' ? ' is-on' : ''}`}>
              <input type="radio" name={`${uid}-mode`} checked={mode === 'read'} onChange={() => setMode('read')} />
              <span className="pdfm-mode__name">Read the whole document</span>
              <span className="pdfm-mode__hint">Every page as text, {priceOf(READ)}</span>
            </label>
            <label className={`pdfm-mode__opt${mode === 'find' ? ' is-on' : ''}`}>
              <input type="radio" name={`${uid}-mode`} checked={mode === 'find'} onChange={() => setMode('find')} />
              <span className="pdfm-mode__name">Search it</span>
              <span className="pdfm-mode__hint">Passages that match, with their page, {priceOf(FIND)}</span>
            </label>
          </div>
        </fieldset>

        {mode === 'find' && (
          <div className="pdfm-search">
            <label className="field__label" htmlFor={`${uid}-q`}>
              Words or a question
            </label>
            <input
              id={`${uid}-q`}
              className="input pdfm-search__input"
              data-testid="field-query"
              type="search"
              value={query}
              placeholder="e.g. architecture"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && canRun && path.trim() && query.trim() && !running) go()
              }}
            />
            <span className="field__hint">Finds exact words and passages close in meaning.</span>
          </div>
        )}

        <div className="pdfm-go">
          <PayButton
            label={label}
            running={running}
            runningLabel={mode === 'read' ? 'Reading the document' : 'Searching the document'}
            disabled={!canRun || !path.trim() || (mode === 'find' && !query.trim())}
            onClick={go}
          />
          {!path.trim() && <span className="field__hint">Choose a PDF first.</span>}
        </div>
      </section>

      {(running || result) && (
        <section className="pdfm-out" aria-labelledby={`${uid}-out`} aria-busy={running}>
          <h2 id={`${uid}-out`} className="visually-hidden">
            The document
          </h2>
          {running && <p className="pdfm-wait">Opening {asked.current.name || 'the PDF'}. Payment settles only if the service succeeds.</p>}
          {!running && result?.isError && (
            <p className="pdfm-fail">
              The service could not {resultTool === FIND ? 'search' : 'read'} this file. Its reply is below. Check that the file is a PDF and that the path is one the service can reach, such as a file you chose above.
            </p>
          )}
          {!running && data && resultTool === READ && typeof data.full_text === 'string' && <Reader data={data as ReadData} name={shownName} />}
          {!running && data && resultTool === FIND && Array.isArray(data.matches) && <Finds data={data as FindData} name={shownName} />}
          {!running && result && <RawOutput text={text} title="The service’s reply" />}
        </section>
      )}
    </div>
  )
}

export default PdfReaderUI
