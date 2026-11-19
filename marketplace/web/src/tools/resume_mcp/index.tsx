import React, { useRef, useState } from 'react'
import { PayButton, RawOutput, getFileUrl } from '../kit'
import type { ToolUIProps } from '../kit'
import { findPath, parseMatch, parseScore, parseSuggestions } from './parse'
import type { Match, Score } from './parse'
import './resume.css'

export const domain = 'resume_mcp'

type Needs = 'resume' | 'resume+job' | 'projects'

interface Action {
  tool: string
  name: string
  gives: string
  verb: string
  needs: Needs
  heading: string
}

const ACTIONS: Action[] = [
  {
    tool: 'resume_score',
    name: 'Score my resume',
    gives: 'A mark out of 100, with points for length, sections, numbers, action verbs and skills.',
    verb: 'score the resume',
    needs: 'resume',
    heading: 'Resume score',
  },
  {
    tool: 'improve_resume',
    name: 'Suggest improvements',
    gives: 'Weak phrases to replace and gaps to fill.',
    verb: 'list improvements',
    needs: 'resume',
    heading: 'Suggested improvements',
  },
  {
    tool: 'resume_to_pdf',
    name: 'Make a PDF',
    gives: 'Your resume text set on a printable page. The first line becomes the title.',
    verb: 'make the PDF',
    needs: 'resume',
    heading: 'Resume PDF',
  },
  {
    tool: 'ats_check',
    name: 'Check the match to a job',
    gives: 'Which skills in the job description your resume shows, and which it lacks.',
    verb: 'check the match',
    needs: 'resume+job',
    heading: 'Match to the job',
  },
  {
    tool: 'cover_letter',
    name: 'Write a cover letter',
    gives: 'A short letter to the company named in the job description.',
    verb: 'write the letter',
    needs: 'resume+job',
    heading: 'Cover letter',
  },
  {
    tool: 'portfolio_generator',
    name: 'Build a portfolio page',
    gives: 'A web page with one section for each project.',
    verb: 'build the page',
    needs: 'projects',
    heading: 'Portfolio page',
  },
]

const GROUPS: { needs: Needs; legend: string }[] = [
  { needs: 'resume', legend: 'Uses your resume' },
  { needs: 'resume+job', legend: 'Uses your resume and the job description' },
  { needs: 'projects', legend: 'Uses your project list' },
]

const SAMPLE_RESUME = `Maya Chen
Backend Engineer

Summary
Backend engineer with six years building payment and data services.

Experience
Senior Engineer, Northwind Payments, 2021 to now
Built a Python and FastAPI settlement service that handles 2 million payments a day.
Reduced failed payouts by 35% by adding retries and idempotency keys.
Responsible for the on-call rota.

Engineer, Tidewater Analytics, 2018 to 2021
Designed PostgreSQL schemas and Airflow pipelines for nightly reporting.

Education
BSc Computer Science, University of Leeds

Skills
Python, FastAPI, PostgreSQL, Docker, AWS, Airflow, Git`

const SAMPLE_JOB = `Harbor Freight Labs is hiring a Platform Engineer.
You will run our payment APIs. Requirements: Python, Kubernetes, PostgreSQL, Terraform, AWS.`

const SAMPLE_PROJECTS = `Settlement service: Python and FastAPI service moving 2 million payments a day
Ledger checker: nightly job that reconciles bank files against the ledger
Payout dashboard: React page that shows failed payouts in real time`

function argsFor(a: Action, resume: string, job: string, projects: string): Record<string, string> {
  if (a.tool === 'resume_to_pdf') return { resume_data: resume }
  if (a.needs === 'projects') return { projects_data: projects }
  if (a.needs === 'resume+job') return { resume_text: resume, job_description: job }
  return { resume_text: resume }
}

function missingFor(a: Action, resume: string, job: string, projects: string): string | null {
  if (a.needs === 'projects') return projects.trim() ? null : 'Add at least one project to build the page.'
  if (!resume.trim()) return 'Paste your resume or load a text file first.'
  if (a.needs === 'resume+job' && !job.trim()) return 'Add the job description; this action reads the company and the skills from it.'
  return null
}

const ResumeDesk: React.FC<ToolUIProps> = (props) => {
  const { tools, run, running, result, resultTool, text, canRun, listing, priceOf, payLabel } = props
  const offered = new Set(tools.map((t) => t.name))
  const actions = ACTIONS.filter((a) => offered.has(a.tool))

  const [resume, setResume] = useState('')
  const [job, setJob] = useState('')
  const [projects, setProjects] = useState('')
  const [pick, setPick] = useState<string>(actions[0]?.tool ?? 'resume_score')
  const [fileNote, setFileNote] = useState<string | null>(null)
  const [tried, setTried] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const action = actions.find((a) => a.tool === pick) ?? actions[0]
  const usingPass = /^Run with your pass/.test(payLabel)
  const missing = action ? missingFor(action, resume, job, projects) : 'This service offers no tools.'
  const label = action ? (usingPass ? `${action.verb[0].toUpperCase()}${action.verb.slice(1)} with your pass` : `Pay ${priceOf(action.tool)} and ${action.verb}`) : 'Run'

  const loadFile = async (f: File) => {
    if (!/\.(txt|md|markdown|text)$/i.test(f.name) && !f.type.startsWith('text/')) {
      setFileNote(`${f.name} is not a plain text file. Open it, copy the text and paste it here.`)
      return
    }
    try {
      const t = await f.text()
      setResume(t)
      setFileNote(`Loaded ${f.name}. Edit it here before you run an action.`)
    } catch {
      setFileNote(`${f.name} could not be read.`)
    }
  }

  const shown = ACTIONS.find((a) => a.tool === resultTool)

  return (
    <div className="resume_mcp">
      <div className="resume_mcp__desk">
        <section className="resume_mcp__material" aria-labelledby="resume_mcp-mat">
          <h2 id="resume_mcp-mat" className="resume_mcp__h">
            Your material
          </h2>

          <div className="resume_mcp__field">
            <div className="resume_mcp__labrow">
              <label htmlFor="resume_mcp-resume" className="resume_mcp__lab">
                Resume
              </label>
              <span className="resume_mcp__tools">
                <input
                  ref={fileRef}
                  type="file"
                  hidden
                  accept=".txt,.md,.markdown,text/plain,text/markdown"
                  data-testid="resume-file"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) loadFile(f)
                    e.target.value = ''
                  }}
                />
                <button type="button" className="resume_mcp__quiet" onClick={() => fileRef.current?.click()} disabled={running}>
                  Load a text file
                </button>
                <button
                  type="button"
                  className="resume_mcp__quiet"
                  disabled={running}
                  onClick={() => {
                    setResume(SAMPLE_RESUME)
                    setJob(SAMPLE_JOB)
                    setProjects(SAMPLE_PROJECTS)
                    setFileNote(null)
                  }}
                >
                  Fill in a sample
                </button>
              </span>
            </div>
            <textarea
              id="resume_mcp-resume"
              className="resume_mcp__area resume_mcp__area--tall"
              data-testid="field-resume_text"
              value={resume}
              onChange={(e) => setResume(e.target.value)}
              placeholder={'Your name on the first line\nThen your experience, education and skills'}
              aria-describedby="resume_mcp-resume-hint"
              disabled={running}
            />
            <p id="resume_mcp-resume-hint" className="resume_mcp__hint" aria-live="polite">
              {fileNote ?? 'Plain text works best. For a PDF or Word file, copy its text in.'}
            </p>
          </div>

          <div className="resume_mcp__field">
            <label htmlFor="resume_mcp-job" className="resume_mcp__lab">
              Job description
              <span className="resume_mcp__opt"> for the match check and the cover letter</span>
            </label>
            <textarea
              id="resume_mcp-job"
              className="resume_mcp__area"
              data-testid="field-job_description"
              value={job}
              onChange={(e) => setJob(e.target.value)}
              placeholder="Paste the job advert, including the company name"
              disabled={running}
            />
          </div>

          <div className="resume_mcp__field">
            <label htmlFor="resume_mcp-proj" className="resume_mcp__lab">
              Projects
              <span className="resume_mcp__opt"> for the portfolio page</span>
            </label>
            <textarea
              id="resume_mcp-proj"
              className="resume_mcp__area"
              data-testid="field-projects_data"
              value={projects}
              onChange={(e) => setProjects(e.target.value)}
              placeholder={'One per line, as Name: what it does\nLedger checker: reconciles bank files nightly'}
              disabled={running}
            />
          </div>
        </section>

        <section className="resume_mcp__actions" aria-labelledby="resume_mcp-act">
          <h2 id="resume_mcp-act" className="resume_mcp__h">
            What to do with it
          </h2>
          {GROUPS.map((g) => {
            const inGroup = actions.filter((a) => a.needs === g.needs)
            if (!inGroup.length) return null
            return (
              <fieldset key={g.needs} className="resume_mcp__group">
                <legend className="resume_mcp__legend">{g.legend}</legend>
                {inGroup.map((a) => (
                  <label key={a.tool} className={`resume_mcp__choice${pick === a.tool ? ' is-picked' : ''}`}>
                    <input
                      type="radio"
                      name="resume_mcp-action"
                      value={a.tool}
                      checked={pick === a.tool}
                      onChange={() => {
                        setPick(a.tool)
                        setTried(false)
                      }}
                      disabled={running}
                      data-testid={`action-${a.tool}`}
                    />
                    <span className="resume_mcp__cname">{a.name}</span>
                    <span className="resume_mcp__cprice">{priceOf(a.tool)}</span>
                    <span className="resume_mcp__cgives">{a.gives}</span>
                  </label>
                ))}
              </fieldset>
            )
          })}

          <div className="resume_mcp__go">
            {tried && missing && (
              <p className="resume_mcp__missing" role="alert">
                {missing}
              </p>
            )}
            <PayButton
              label={label}
              running={running}
              disabled={!canRun || listing.online === false || !action}
              onClick={() => {
                setTried(true)
                if (!action || missing) return
                run({ tool: action.tool, args: argsFor(action, resume, job, projects) })
              }}
            />
          </div>
        </section>
      </div>

      {(running || result) && (
        <section className="resume_mcp__out" aria-labelledby="resume_mcp-out" aria-busy={running}>
          <h2 id="resume_mcp-out" className="resume_mcp__h">
            {running ? 'Working on it' : shown?.heading ?? 'Result'}
          </h2>
          {running && (
            <p className="resume_mcp__wait" role="status">
              Waiting for the wallet and the service. You pay only if the action succeeds.
            </p>
          )}
          {result && !running && (
            <>
              {result.isError ? (
                <p className="resume_mcp__err">The service could not do this. Its reason is in the response below.</p>
              ) : (
                <ResultView tool={resultTool} text={text} />
              )}
              <RawOutput text={text} />
            </>
          )}
        </section>
      )}
    </div>
  )
}

const ResultView: React.FC<{ tool: string | null; text: string }> = ({ tool, text }) => {
  switch (tool) {
    case 'resume_score': {
      const s = parseScore(text)
      return s ? <ScoreView s={s} /> : null
    }
    case 'ats_check': {
      const m = parseMatch(text)
      return m ? <MatchView m={m} /> : null
    }
    case 'improve_resume':
      return <SuggestionsView text={text} />
    case 'cover_letter':
      return <LetterView text={text} />
    case 'resume_to_pdf': {
      const p = findPath(text, 'pdf')
      return p ? <PdfView path={p} /> : null
    }
    case 'portfolio_generator': {
      const p = findPath(text, 'html')
      return p ? <PortfolioView path={p} /> : null
    }
    default:
      return null
  }
}

const ScoreView: React.FC<{ s: Score }> = ({ s }) => (
  <div className="resume_mcp__score" data-testid="resume-score">
    <p className="resume_mcp__big">
      <span className="resume_mcp__bignum">{s.total}</span>
      <span className="resume_mcp__bigof">out of 100</span>
    </p>
    <div className="resume_mcp__breakdown">
      <table className="resume_mcp__parts">
        <caption className="resume_mcp__cap">Where the points came from</caption>
        <tbody>
          {s.parts.map((p) => (
            <tr key={p.label}>
              <th scope="row">
                {p.label}
                <span className="resume_mcp__pdetail">{p.detail}</span>
              </th>
              <td className="resume_mcp__barcell" aria-hidden="true">
                <span className="resume_mcp__bar">
                  <span className="resume_mcp__fill" style={{ width: `${p.max ? (100 * p.points) / p.max : 0}%` }} />
                </span>
              </td>
              <td className="resume_mcp__pts">
                {p.points} of {p.max}
              </td>
            </tr>
          ))}
          {s.penalty && (
            <tr className="resume_mcp__pen">
              <th scope="row">
                Weak phrases
                <span className="resume_mcp__pdetail">{s.penalty.detail}</span>
              </th>
              <td className="resume_mcp__barcell" aria-hidden="true" />
              <td className="resume_mcp__pts">{s.penalty.points ? `minus ${s.penalty.points}` : 'none'}</td>
            </tr>
          )}
        </tbody>
      </table>
      {s.tips.length > 0 && (
        <div className="resume_mcp__tips">
          <h3 className="resume_mcp__h3">To raise the score</h3>
          <ul>
            {s.tips.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  </div>
)

const MatchView: React.FC<{ m: Match }> = ({ m }) => (
  <div className="resume_mcp__score" data-testid="resume-match">
    <p className="resume_mcp__big">
      <span className="resume_mcp__bignum">{m.pct}%</span>
      <span className="resume_mcp__bigof">of the skills the job names</span>
    </p>
    <div className="resume_mcp__breakdown">
      {m.matched.length + m.missing.length === 0 && (
        <p>The job description names no skills this checker knows, so there is nothing to match.</p>
      )}
      {m.matched.length > 0 && (
        <div>
          <h3 className="resume_mcp__h3">Your resume shows</h3>
          <ul className="resume_mcp__chips">
            {m.matched.map((x) => (
              <li key={x} className="resume_mcp__chip">
                {x}
              </li>
            ))}
          </ul>
        </div>
      )}
      {m.missing.length > 0 && (
        <div>
          <h3 className="resume_mcp__h3">Missing from your resume</h3>
          <ul className="resume_mcp__chips">
            {m.missing.map((x) => (
              <li key={x} className="resume_mcp__chip resume_mcp__chip--missing">
                {x}
              </li>
            ))}
          </ul>
          <p className="resume_mcp__hint">Add the ones you really have, in your own words, near the work where you used them.</p>
        </div>
      )}
    </div>
  </div>
)

const SuggestionsView: React.FC<{ text: string }> = ({ text }) => {
  const items = parseSuggestions(text)
  if (!items.length) return <p className="resume_mcp__ok">{text.trim() || 'No suggestions.'}</p>
  return (
    <ul className="resume_mcp__suggest" data-testid="resume-suggestions">
      {items.map((t) => (
        <li key={t}>{t}</li>
      ))}
    </ul>
  )
}

const LetterView: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState<string | null>(null)
  const paras = text.trim().split(/\n{2,}/)
  return (
    <div className="resume_mcp__letterwrap">
      <article className="resume_mcp__letter" data-testid="resume-letter">
        {paras.map((p, i) => (
          <p key={i}>
            {p.split('\n').map((l, j) => (
              <React.Fragment key={j}>
                {j > 0 && <br />}
                {l}
              </React.Fragment>
            ))}
          </p>
        ))}
      </article>
      <div className="resume_mcp__copyrow">
        <button
          type="button"
          className="resume_mcp__quiet resume_mcp__quiet--boxed"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(text.trim())
              setCopied('Copied the letter.')
            } catch {
              setCopied('The browser blocked copying. Select the letter and copy it by hand.')
            }
          }}
        >
          Copy the letter
        </button>
        <span className="resume_mcp__hint" aria-live="polite">
          {copied}
        </span>
      </div>
    </div>
  )
}

const PdfView: React.FC<{ path: string }> = ({ path }) => {
  const url = getFileUrl(path)
  return (
    <div>
      <iframe className="resume_mcp__frame" src={url} title="Resume PDF" />
      <p className="resume_mcp__links">
        <a href={url} download="resume.pdf">
          Download the PDF
        </a>
        <a href={url} target="_blank" rel="noopener noreferrer">
          Open in a new tab
        </a>
      </p>
    </div>
  )
}

const PortfolioView: React.FC<{ path: string }> = ({ path }) => {
  const url = getFileUrl(path)
  return (
    <div>
      <iframe className="resume_mcp__frame resume_mcp__frame--page" src={url} sandbox="" title="Portfolio page preview" />
      <p className="resume_mcp__links">
        <a href={url} target="_blank" rel="noopener noreferrer">
          Open the page in a new tab
        </a>
        <a href={url} download="portfolio.html">
          Download the HTML
        </a>
      </p>
    </div>
  )
}

export default ResumeDesk
