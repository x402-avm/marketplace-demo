import React, { useEffect, useId, useMemo, useRef, useState } from 'react'
import { PayButton, RawOutput, UploadButton, fileName } from '../kit'
import type { ToolUIProps } from '../kit'
import { payloads } from './pyrepr'
import './pdf_reader_mcp.css'

export const domain = 'pdf_reader_mcp'

type Mode = 'ask' | 'read' | 'check'

const TOOL: Record<Mode, string> = { ask: 'search_pdf', read: 'read_pdf', check: 'pdf_evidence' }

interface Source {
  path: string
  name: string
}

interface Match {
  page: number
  snippet?: string
  text?: string
  id?: string
  [k: string]: any
}

interface Block {
  source: string
  success?: boolean
  matches?: Match[]
  total_matches?: number
  num_pages?: number
  searched_pages?: number[] | number
  data?: any
  error?: string
}

const STOP = new Set(['the', 'and', 'for', 'with', 'that', 'this', 'from', 'are', 'was', 'were', 'what', 'which', 'how', 'does', 'into', 'who', 'when', 'where', 'why', 'about', 'there', 'their'])

function keywordsOf(q: string): string[] {
  const words = q
    .split(/\s+/)
    .map((w) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ''))
    .filter((w) => w.length > 2 && !STOP.has(w.toLowerCase()))
  return Array.from(new Set(words))
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const Marked: React.FC<{ text: string; terms: string[] }> = ({ text, terms }) => {
  const list = terms.filter(Boolean).sort((a, b) => b.length - a.length)
  if (!list.length) return <>{text}</>
  const parts = text.split(new RegExp(`(${list.map(escapeRe).join('|')})`, 'giu'))
  return (
    <>
      {parts.map((p, i) => (i % 2 === 1 ? <mark key={i} className="pdfe-mark">{p}</mark> : <React.Fragment key={i}>{p}</React.Fragment>))}
    </>
  )
}

const CopyButton: React.FC<{ text: string; label: string }> = ({ text, label }) => {
  const [done, setDone] = useState(false)
  useEffect(() => {
    if (!done) return
    const t = window.setTimeout(() => setDone(false), 1800)
    return () => window.clearTimeout(t)
  }, [done])
  return (
    <button
      type="button"
      className="pdfe-copy"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setDone(true)
        } catch {
          setDone(false)
        }
      }}
    >
      <span aria-live="polite">{done ? 'Copied' : label}</span>
    </button>
  )
}

/** Every per-file block in the reply, whichever tool produced it. */
function blocksOf(text: string): Block[] {
  const out: Block[] = []
  for (const p of payloads(text)) {
    if (!Array.isArray(p?.results)) continue
    for (const r of p.results) if (r && typeof r === 'object') out.push(r as Block)
  }
  return out
}

const nameFor = (path: string, names: Record<string, string>) => names[path] || fileName(path)

/* ---------- ask: evidence cards ---------- */

const Evidence: React.FC<{ blocks: Block[]; query: string; names: Record<string, string> }> = ({ blocks, query, names }) => {
  const words = useMemo(() => keywordsOf(query), [query])
  const total = blocks.reduce((n, b) => n + (b.matches?.length ?? 0), 0)

  if (!total) {
    return (
      <div className="pdfe-none">
        <h3 className="pdfe-h3">No passage says that</h3>
        <p className="pdfe-muted">
          {blocks.length > 1 ? 'None of these files' : 'This file'} contains the exact wording “{query}”. The search matches the words themselves, so a short phrase works better than a full question.
        </p>
        {words.length > 0 && <p className="pdfe-muted">Words from your question to try on their own: {words.join(', ')}.</p>}
      </div>
    )
  }

  return (
    <div className="pdfe-evidence">
      <header className="pdfe-evidence__head">
        <h3 className="pdfe-h3">
          {total === 1 ? 'One passage' : `${total} passages`} found for “{query}”
        </h3>
        <p className="pdfe-muted">
          {blocks
            .map((b) => `${nameFor(b.source, names)}: ${b.matches?.length ?? 0}`)
            .join(', ')}
        </p>
      </header>
      {blocks.map((b) =>
        (b.matches ?? []).length === 0 ? null : (
          <section key={b.source} className="pdfe-file" aria-label={`Evidence from ${nameFor(b.source, names)}`}>
            <h4 className="pdfe-file__name">{nameFor(b.source, names)}</h4>
            <ul className="pdfe-cards">
              {(b.matches ?? []).map((m, i) => {
                const quote = (m.snippet ?? m.excerpt ?? '').toString().replace(/\s*\n\s*/g, ' ').trim()
                const cite = `“${quote}” (${nameFor(b.source, names)}, page ${m.page})`
                return (
                  <li key={m.id ?? i} className="pdfe-card">
                    <div className="pdfe-card__tab" aria-hidden="true">
                      <span className="pdfe-card__pg">p.</span>
                      <span className="pdfe-card__num">{m.page}</span>
                    </div>
                    <div className="pdfe-card__main">
                      <blockquote className="pdfe-card__quote">
                        <Marked text={quote} terms={[...(m.text ? [String(m.text)] : []), ...words]} />
                      </blockquote>
                      <p className="pdfe-card__src">
                        <span className="visually-hidden">From </span>
                        {nameFor(b.source, names)}, page {m.page}
                      </p>
                      <CopyButton text={cite} label="Copy as a citation" />
                    </div>
                  </li>
                )
              })}
            </ul>
          </section>
        ),
      )}
      {blocks.some((b) => (b.matches ?? []).length === 0) && (
        <p className="pdfe-muted">
          Nothing in {blocks.filter((b) => !(b.matches ?? []).length).map((b) => nameFor(b.source, names)).join(', ')}.
        </p>
      )}
    </div>
  )
}

/* ---------- read and check: one card per file ---------- */

const PROFILE: Record<string, string> = {
  digital_text: 'Has selectable text',
  scanned: 'Looks scanned, text may need OCR',
  mixed: 'Part text, part scanned pages',
}

const Files: React.FC<{ blocks: Block[]; names: Record<string, string>; mode: Mode }> = ({ blocks, names, mode }) => {
  // inspect replies hold two blocks per file (the check, then the reading); fold them together by file
  const byFile = new Map<string, { sig?: any; read?: any; error?: string }>()
  for (const b of blocks) {
    const cur = byFile.get(b.source) ?? {}
    if (b.success === false) cur.error = b.error || 'The service could not open this file.'
    const d = b.data ?? {}
    if (d.profile || d.page_signals) cur.sig = d
    if (typeof d.full_text === 'string' || d.info) cur.read = { ...(cur.read ?? {}), ...d }
    if (d.num_pages && !cur.read) cur.read = { num_pages: d.num_pages }
    byFile.set(b.source, cur)
  }
  return (
    <ul className="pdfe-files">
      {Array.from(byFile.entries()).map(([src, f]) => {
        const pages = f.sig?.num_pages ?? f.read?.num_pages
        const needsOcr = f.sig?.recommendation?.needs_ocr
        const info = f.read?.info ?? {}
        const facts: [string, string][] = []
        if (info.Title && info.Title !== 'untitled') facts.push(['Title', info.Title])
        if (info.Author && info.Author !== 'anonymous') facts.push(['Author', info.Author])
        if (info.Producer) facts.push(['Made with', info.Producer])
        const full: string | undefined = f.read?.full_text
        return (
          <li key={src} className="pdfe-file pdfe-file--card">
            <h4 className="pdfe-file__name">{nameFor(src, names)}</h4>
            {f.error && <p className="pdfe-fail">{f.error}</p>}
            <p className="pdfe-muted">
              {pages ? (pages === 1 ? 'One page' : `${pages} pages`) : 'Page count not reported'}
              {f.sig?.profile ? `. ${PROFILE[f.sig.profile] ?? f.sig.profile.replace(/_/g, ' ')}` : ''}
              {needsOcr === true ? '. OCR recommended.' : needsOcr === false ? '. No OCR needed.' : ''}
            </p>
            {facts.length > 0 && (
              <dl className="pdfe-facts">
                {facts.map(([k, v]) => (
                  <React.Fragment key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </React.Fragment>
                ))}
              </dl>
            )}
            {Array.isArray(f.sig?.page_signals) && f.sig.page_signals.length > 0 && (
              <table className="pdfe-table">
                <thead>
                  <tr>
                    <th scope="col">Page</th>
                    <th scope="col">Characters</th>
                    <th scope="col">Likely scanned</th>
                  </tr>
                </thead>
                <tbody>
                  {f.sig.page_signals.map((p: any) => (
                    <tr key={p.page}>
                      <td>{p.page}</td>
                      <td>{p.text_chars}</td>
                      <td>{p.likely_scanned ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {full !== undefined && (
              <div className="pdfe-text">
                <div className="pdfe-text__head">
                  <span className="pdfe-muted">Text of the file</span>
                  <CopyButton text={full} label="Copy text" />
                </div>
                <div className="pdfe-text__body" tabIndex={0} role="region" aria-label={`Text of ${nameFor(src, names)}`}>
                  {full.trim() ? full.split(/\n\s*\n+/).filter((p) => p.trim()).map((p, i) => <p key={i}>{p.trim()}</p>) : <p className="pdfe-muted">No text was found. This may be a scan.</p>}
                </div>
              </div>
            )}
            {mode === 'read' && full === undefined && <p className="pdfe-muted">Text was left out, as you asked.</p>}
          </li>
        )
      })}
    </ul>
  )
}

/* ---------- the page ---------- */

const PdfEvidence: React.FC<ToolUIProps> = (props) => {
  const { running, result, resultTool, text, canRun, priceOf, payLabel } = props
  const uid = useId()
  const [sources, setSources] = useState<Source[]>([])
  const [pathInput, setPathInput] = useState('')
  const [mode, setMode] = useState<Mode>('ask')
  const [query, setQuery] = useState('')
  const [fullText, setFullText] = useState(true)
  const [ocrLayer, setOcrLayer] = useState(false)
  const [samplePages, setSamplePages] = useState('')
  const sent = useRef<{ mode: Mode; query: string; names: Record<string, string> }>({ mode: 'ask', query: '', names: {} })

  const withPass = payLabel.startsWith('Run with')
  const tool = TOOL[mode]
  const names = useMemo(() => Object.fromEntries(sources.map((s) => [s.path, s.name])), [sources])

  const addPath = (path: string, name?: string) => {
    const p = path.trim()
    if (!p) return
    setSources((cur) => (cur.some((s) => s.path === p) ? cur : [...cur, { path: p, name: name || fileName(p) }]))
  }

  const ready = sources.length > 0 && (mode !== 'ask' || query.trim().length > 0)
  const verb = mode === 'ask' ? 'ask' : mode === 'read' ? 'read' : 'check'
  const label = withPass
    ? `${verb[0].toUpperCase()}${verb.slice(1)} with your pass`
    : `Pay ${priceOf(tool)} and ${mode === 'ask' ? 'search for evidence' : mode === 'read' ? 'read the files' : 'check the files'}`

  const go = () => {
    const srcs = sources.map((s) => ({ path: s.path }))
    sent.current = { mode, query: query.trim(), names }
    if (mode === 'ask') props.run({ tool, args: { sources: srcs, query: query.trim() } })
    else if (mode === 'check') props.run({ tool, args: { operation: 'inspect', sources: srcs } })
    else {
      const args: Record<string, any> = { sources: srcs, include_full_text: fullText }
      const n = parseInt(samplePages, 10)
      if (n > 0) args.sample_pages = n
      if (ocrLayer) args.include_ocr_text_layer = true
      props.run({ tool, args })
    }
  }

  const blocks = useMemo(() => (result && !result.isError ? blocksOf(text) : []), [result, text])
  const shown = resultTool === 'search_pdf' ? 'ask' : resultTool === 'read_pdf' ? 'read' : 'check'

  return (
    <div className="pdfe">
      <section className="pdfe-in" aria-labelledby={`${uid}-src`}>
        <h2 id={`${uid}-src`} className="svc__h2">
          Your files
        </h2>
        {sources.length === 0 ? (
          <p className="pdfe-muted pdfe-empty">Add one PDF or several. The search runs across all of them and tells you which file each passage came from.</p>
        ) : (
          <ul className="pdfe-sources" data-testid="field-sources" aria-label="Files to search">
            {sources.map((s) => (
              <li key={s.path} className="pdfe-source">
                <span className="pdfe-source__name">{s.name}</span>
                <button
                  type="button"
                  className="pdfe-source__x"
                  aria-label={`Remove ${s.name}`}
                  onClick={() => setSources((cur) => cur.filter((c) => c.path !== s.path))}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="pdfe-add">
          <UploadButton accept="application/pdf,.pdf" label={sources.length ? 'Add another PDF' : 'Choose a PDF'} testid="pdfe-upload" onPath={(p, f) => addPath(p, f.name)} />
          <div className="pdfe-add__path">
            <label className="visually-hidden" htmlFor={`${uid}-path`}>
              Path of a PDF on the service
            </label>
            <input
              id={`${uid}-path`}
              className="input"
              data-testid="pdfe-path"
              value={pathInput}
              placeholder="Or paste a path on the service"
              spellCheck={false}
              onChange={(e) => setPathInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addPath(pathInput)
                  setPathInput('')
                }
              }}
            />
            <button
              type="button"
              className="btn btn--quiet"
              disabled={!pathInput.trim()}
              onClick={() => {
                addPath(pathInput)
                setPathInput('')
              }}
            >
              Add path
            </button>
          </div>
        </div>

        <fieldset className="pdfe-mode" data-testid="field-operation">
          <legend className="field__label">What do you need</legend>
          {(
            [
              ['ask', 'Find evidence for a question', 'Quoted passages with file and page'],
              ['read', 'Read the files', 'Text and details, with options'],
              ['check', 'Check what kind of PDF it is', 'Text or scan, page by page'],
            ] as [Mode, string, string][]
          ).map(([m, name, hint]) => (
            <label key={m} className={`pdfe-mode__opt${mode === m ? ' is-on' : ''}`}>
              <input type="radio" name={`${uid}-mode`} checked={mode === m} onChange={() => setMode(m)} />
              <span className="pdfe-mode__name">{name}</span>
              <span className="pdfe-mode__hint">
                {hint}, {priceOf(TOOL[m])}
              </span>
            </label>
          ))}
        </fieldset>

        {mode === 'ask' && (
          <div className="pdfe-q">
            <label className="field__label" htmlFor={`${uid}-q`}>
              Question or wording to look for
            </label>
            <input
              id={`${uid}-q`}
              className="input pdfe-q__input"
              data-testid="field-query"
              type="search"
              value={query}
              placeholder="e.g. architecture"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && canRun && ready && !running) go()
              }}
            />
            <span className="field__hint">Passages are found by their wording, so a few key words work best.</span>
          </div>
        )}

        {mode === 'read' && (
          <div className="pdfe-opts">
            <label className="pdfe-check">
              <input type="checkbox" data-testid="field-include_full_text" checked={fullText} onChange={(e) => setFullText(e.target.checked)} />
              <span>Include the full text</span>
            </label>
            <label className="pdfe-check">
              <input type="checkbox" data-testid="field-include_ocr_text_layer" checked={ocrLayer} onChange={(e) => setOcrLayer(e.target.checked)} />
              <span>Include the text layer added by OCR</span>
            </label>
            <div className="pdfe-opts__n">
              <label className="field__label" htmlFor={`${uid}-n`}>
                Pages to sample
              </label>
              <input
                id={`${uid}-n`}
                className="input"
                data-testid="field-sample_pages"
                type="number"
                min={1}
                inputMode="numeric"
                value={samplePages}
                placeholder="All"
                onChange={(e) => setSamplePages(e.target.value)}
              />
            </div>
          </div>
        )}

        <div className="pdfe-go">
          <PayButton
            label={label}
            running={running}
            runningLabel={mode === 'ask' ? 'Looking through the files' : mode === 'read' ? 'Reading the files' : 'Checking the files'}
            disabled={!canRun || !ready}
            onClick={go}
          />
          {sources.length === 0 && <span className="field__hint">Add a PDF first.</span>}
          {sources.length > 0 && mode === 'ask' && !query.trim() && <span className="field__hint">Write what to look for.</span>}
        </div>
      </section>

      {(running || result) && (
        <section className="pdfe-out" aria-labelledby={`${uid}-out`} aria-busy={running}>
          <h2 id={`${uid}-out`} className="visually-hidden">
            Evidence
          </h2>
          {running && <p className="pdfe-muted">Working through {sources.length === 1 ? sources[0].name : `${sources.length} files`}. Payment settles only if the service succeeds.</p>}
          {!running && result?.isError && (
            <p className="pdfe-fail">
              The service could not use these files. Its reply is below. Each file must be a PDF, chosen with the button above or a path the service can reach.
            </p>
          )}
          {!running && !result?.isError && result && blocks.length > 0 && shown === 'ask' && <Evidence blocks={blocks} query={sent.current.query} names={sent.current.names} />}
          {!running && !result?.isError && result && blocks.length > 0 && shown !== 'ask' && <Files blocks={blocks} names={sent.current.names} mode={shown} />}
          {!running && result && <RawOutput text={text} title="The service’s reply" />}
        </section>
      )}
    </div>
  )
}

export default PdfEvidence
