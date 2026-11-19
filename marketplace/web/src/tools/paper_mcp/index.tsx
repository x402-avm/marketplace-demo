import React, { useId, useState } from 'react'
import { PayButton, RawOutput, parseJson } from '../kit'
import type { ToolUIProps } from '../kit'
import './paper.css'

export const domain = 'paper_mcp'

const TOOL = 'search_papers'
const MIN = 1
const MAX = 10
const SUGGESTIONS = ['graph neural networks', 'retrieval augmented generation', 'protein structure prediction', 'quantum error correction']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

interface Paper {
  title?: string
  authors?: string[]
  summary?: string
  pdf_url?: string
}

/** arXiv ids carry the submission year and month (2306.14753v1 is June 2023, version 1). */
function arxivFacts(pdf?: string) {
  if (!pdf) return null
  const m = pdf.match(/arxiv\.org\/(?:pdf|abs)\/((\d{2})(\d{2})\.\d{4,5})(?:v(\d+))?/i)
  if (m) {
    const month = Number(m[3])
    return {
      id: m[1],
      when: month >= 1 && month <= 12 ? `${MONTHS[month - 1]} 20${m[2]}` : null,
      version: m[4] ?? null,
      abs: `https://arxiv.org/abs/${m[1]}`,
    }
  }
  const old = pdf.match(/arxiv\.org\/(?:pdf|abs)\/([a-z-]+(?:\.[A-Z]{2})?\/\d{7})(?:v(\d+))?/i)
  if (old) return { id: old[1], when: null, version: old[2] ?? null, abs: `https://arxiv.org/abs/${old[1]}` }
  return null
}

function explainError(text: string): string {
  if (/connection error/i.test(text)) return 'arXiv did not answer within 30 seconds. It is often slow for a minute at a time; search again shortly.'
  if (/temporarily unavailable/i.test(text)) return 'arXiv is refusing requests for the moment, usually because of rate limits. Wait a minute and search again.'
  return 'The search did not finish. The service’s own message is below.'
}

const PaperEntry: React.FC<{ paper: Paper; rank: number }> = ({ paper, rank }) => {
  const [open, setOpen] = useState(false)
  const [allAuthors, setAllAuthors] = useState(false)
  const excerptId = useId()
  const facts = arxivFacts(paper.pdf_url)
  const authors = paper.authors ?? []
  const shown = allAuthors ? authors : authors.slice(0, 3)
  const hidden = authors.length - shown.length
  const excerpt = (paper.summary ?? '').replace(/\s+/g, ' ').trim()
  const long = excerpt.length > 180

  return (
    <li className="paper_mcp__paper">
      <span className="paper_mcp__rank" aria-hidden="true">
        {rank}
      </span>
      <div className="paper_mcp__body">
        <h3 className="paper_mcp__title">
          {facts ? (
            <a href={facts.abs} target="_blank" rel="noreferrer">
              {paper.title?.replace(/\s+/g, ' ') || 'Untitled paper'}
            </a>
          ) : (
            paper.title?.replace(/\s+/g, ' ') || 'Untitled paper'
          )}
        </h3>
        {authors.length > 0 && (
          <p className="paper_mcp__authors">
            {shown.join(', ')}
            {hidden > 0 && (
              <>
                {' '}
                <button type="button" className="paper_mcp__more" onClick={() => setAllAuthors(true)}>
                  and {hidden} more
                </button>
              </>
            )}
          </p>
        )}
        {facts && (
          <p className="paper_mcp__meta">
            <span>arXiv {facts.id}</span>
            {facts.when && <span>submitted {facts.when}</span>}
            {facts.version && <span>version {facts.version}</span>}
          </p>
        )}
        {excerpt && (
          <div className="paper_mcp__abstract">
            <p id={excerptId} className={`paper_mcp__excerpt${open || !long ? ' is-open' : ''}`}>
              {excerpt}
            </p>
            {long && (
              <button type="button" className="paper_mcp__toggle" aria-expanded={open} aria-controls={excerptId} onClick={() => setOpen(!open)}>
                {open ? 'Show less of the abstract' : 'Show more of the abstract'}
              </button>
            )}
          </div>
        )}
        {facts && (
          <p className="paper_mcp__links">
            <a href={facts.abs} target="_blank" rel="noreferrer">
              Full abstract on arXiv
            </a>
            {paper.pdf_url && (
              <a href={paper.pdf_url} target="_blank" rel="noreferrer">
                Download the PDF
              </a>
            )}
          </p>
        )}
      </div>
    </li>
  )
}

const PaperSearch: React.FC<ToolUIProps> = (p) => {
  const query: string = p.args.query ?? ''
  const count: number = Number.isFinite(p.args.max_results) ? p.args.max_results : 5
  const [searched, setSearched] = useState('')
  const set = (patch: Record<string, any>) => p.setArgs({ query, max_results: count, ...p.args, ...patch })
  const clamp = (n: number) => Math.min(MAX, Math.max(MIN, Math.round(n) || MIN))
  const withPass = p.payLabel.startsWith('Run with')
  const label = withPass ? 'Search arXiv with your pass' : `Pay ${p.priceOf(TOOL)} and search arXiv`
  const canSearch = p.canRun && query.trim().length > 0

  const search = () => {
    if (!canSearch || p.running) return
    setSearched(query.trim())
    p.run({ tool: TOOL, args: { query: query.trim(), max_results: count } })
  }

  const showResult = p.result && p.resultTool === TOOL
  const data = showResult && !p.result?.isError ? parseJson<{ papers?: Paper[] }>(p.text) : null
  const papers = data?.papers ?? null

  return (
    <div className="paper_mcp">
      <form
        className="paper_mcp__bar"
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          search()
        }}
      >
        <div className="paper_mcp__query">
          <label htmlFor="paper-query" className="paper_mcp__label">
            Search arXiv papers
          </label>
          <input
            id="paper-query"
            type="search"
            className="paper_mcp__input"
            data-testid="field-query"
            value={query}
            placeholder="Words from a title, abstract or author name"
            disabled={p.running}
            onChange={(e) => set({ query: e.target.value })}
          />
        </div>
        <div className="paper_mcp__count">
          <label htmlFor="paper-count" className="paper_mcp__label">
            Papers
          </label>
          <div className="paper_mcp__stepper">
            <button type="button" aria-label="Fewer papers" disabled={p.running || count <= MIN} onClick={() => set({ max_results: clamp(count - 1) })}>
              −
            </button>
            <input
              id="paper-count"
              type="number"
              inputMode="numeric"
              min={MIN}
              max={MAX}
              data-testid="field-max_results"
              value={count}
              disabled={p.running}
              onChange={(e) => set({ max_results: clamp(Number(e.target.value)) })}
            />
            <button type="button" aria-label="More papers" disabled={p.running || count >= MAX} onClick={() => set({ max_results: clamp(count + 1) })}>
              +
            </button>
          </div>
        </div>
        <div className="paper_mcp__go">
          <PayButton label={label} running={p.running} runningLabel="Searching arXiv" disabled={!canSearch} onClick={search} />
        </div>
      </form>

      <div className="paper_mcp__results" aria-live="polite">
        {!showResult && !p.running && (
          <div className="paper_mcp__empty">
            <p>Search returns the best matches from arXiv, with authors, an excerpt of the abstract and a link to each PDF. One search is one payment, whatever the number of papers.</p>
            <p className="paper_mcp__try">
              <span>Try</span>
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="paper_mcp__suggest" onClick={() => set({ query: s })}>
                  {s}
                </button>
              ))}
            </p>
          </div>
        )}

        {p.running && <p className="paper_mcp__wait">Asking arXiv for {count === 1 ? 'one paper' : `${count} papers`} about “{searched || query}”. This usually takes a few seconds.</p>}

        {showResult && p.result?.isError && <p className="paper_mcp__problem">{explainError(p.text)}</p>}

        {papers && papers.length === 0 && <p className="paper_mcp__problem">arXiv found no papers for “{searched}”. Try fewer or more general words.</p>}

        {papers && papers.length > 0 && (
          <>
            <p className="paper_mcp__summary">
              {papers.length === 1 ? 'One paper' : `${papers.length} papers`} for “{searched || query}”, most relevant first
            </p>
            <ol className="paper_mcp__list">
              {papers.map((paper, i) => (
                <PaperEntry key={(paper.pdf_url ?? '') + i} paper={paper} rank={i + 1} />
              ))}
            </ol>
          </>
        )}

        {showResult && <RawOutput text={p.text} title="What the service sent back" />}
      </div>
    </div>
  )
}

export default PaperSearch
