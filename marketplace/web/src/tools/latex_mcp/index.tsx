import React, { useMemo, useRef, useState } from 'react'
import { PayButton, RawOutput, getFileUrl } from '../kit'
import type { ToolUIProps } from '../kit'
import { STARTERS } from './templates'
import './latex.css'

export const domain = 'latex_mcp'

const TOOL = 'compile_latex_to_pdf'
const LINE_PX = 21

interface TexProblem {
  message: string
  line: number | null
}

/** Pull "! message" / "l.<n> ..." pairs (and "on input line n") out of a pdflatex log. */
export function parseProblems(log: string): TexProblem[] {
  const lines = log.split('\n')
  const out: TexProblem[] = []
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i]
    if (!l.startsWith('! ')) continue
    let message = l.slice(2).trim()
    let line: number | null = null
    for (let j = i + 1; j < Math.min(lines.length, i + 12); j++) {
      const at = lines[j].match(/^l\.(\d+)/)
      if (at) {
        line = Number(at[1])
        break
      }
      const onInput = lines[j].match(/on input line (\d+)/)
      if (onInput) {
        line = Number(onInput[1])
        break
      }
      if (lines[j].startsWith('! ')) break
      // A wrapped continuation of the message itself
      if (j === i + 1 && /^[a-z]/i.test(lines[j]) && !/^(See|Type|You|\(|l\.)/.test(lines[j])) message += ' ' + lines[j].trim()
    }
    const inline = message.match(/on input line (\d+)/)
    if (line === null && inline) line = Number(inline[1])
    message = message.replace(/^LaTeX Error:\s*/, '').replace(/\s*See the LaTeX manual.*$/, '')
    if (!out.some((p) => p.message === message && p.line === line)) out.push({ message, line })
  }
  return out
}

function compileLabel(payLabel: string): string {
  if (/^Run with your pass/.test(payLabel)) return 'Compile with your pass'
  return payLabel.replace(/ and run$/, ' and compile')
}

const LatexDesk: React.FC<ToolUIProps> = (props) => {
  const { args, setArgs, run, running, result, text, canRun, listing } = props
  const source: string = typeof args.latex_string === 'string' ? args.latex_string : STARTERS[0].source
  const [starter, setStarter] = useState<string>(typeof args.latex_string === 'string' ? '' : STARTERS[0].id)
  const [focusLine, setFocusLine] = useState<number | null>(null)
  const areaRef = useRef<HTMLTextAreaElement>(null)
  const gutterRef = useRef<HTMLDivElement>(null)

  const setSource = (s: string) => setArgs({ ...args, latex_string: s })
  const lineCount = source.split('\n').length

  const done = Boolean(result) && props.resultTool === TOOL
  const failed = done && Boolean(result?.isError)
  const pdfPath = done && !failed ? (text.match(/\/[^\s'"]+\.pdf/) || [])[0] : undefined
  const problems = useMemo(() => (failed ? parseProblems(text) : []), [failed, text])
  const badLines = new Set(problems.map((p) => p.line).filter((n): n is number => n !== null))

  const goToLine = (n: number) => {
    const ta = areaRef.current
    if (!ta) return
    const ls = ta.value.split('\n')
    const idx = Math.max(0, Math.min(n, ls.length) - 1)
    let start = 0
    for (let i = 0; i < idx; i++) start += ls[i].length + 1
    ta.focus()
    ta.setSelectionRange(start, start + ls[idx].length)
    ta.scrollTop = Math.max(0, idx * LINE_PX - ta.clientHeight / 3)
    if (gutterRef.current) gutterRef.current.scrollTop = ta.scrollTop
    setFocusLine(n)
  }

  const pickStarter = (id: string) => {
    const s = STARTERS.find((x) => x.id === id)
    if (!s) return
    setStarter(id)
    setFocusLine(null)
    setSource(s.source)
  }

  return (
    <div className="latex_mcp">
      <div className="latex_mcp__desk">
        <section className="latex_mcp__source" aria-labelledby="latex_mcp-src">
          <div className="latex_mcp__bar">
            <h2 id="latex_mcp-src" className="latex_mcp__h">
              Source
            </h2>
            <div className="latex_mcp__starters" role="group" aria-label="Start from a template">
              <span className="latex_mcp__starthint">Start from</span>
              {STARTERS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="latex_mcp__starter"
                  aria-pressed={starter === s.id}
                  onClick={() => pickStarter(s.id)}
                  disabled={running}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>

          <div className="latex_mcp__editor">
            <div className="latex_mcp__gutter" ref={gutterRef} aria-hidden="true">
              {Array.from({ length: lineCount }, (_, i) => {
                const n = i + 1
                const cls = badLines.has(n) ? ' is-bad' : n === focusLine ? ' is-focus' : ''
                return (
                  <div key={n} className={`latex_mcp__ln${cls}`}>
                    {n}
                  </div>
                )
              })}
            </div>
            <textarea
              ref={areaRef}
              className="latex_mcp__area"
              data-testid="field-latex_string"
              aria-label="LaTeX source"
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              wrap="off"
              value={source}
              disabled={running}
              onChange={(e) => {
                setStarter('')
                setSource(e.target.value)
              }}
              onScroll={(e) => {
                if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop
              }}
              onKeyDown={(e) => {
                // Tab inserts two spaces; Escape then Tab leaves the editor, as usual for code fields.
                if (e.key === 'Tab' && !e.shiftKey && !(e.currentTarget.dataset.escaped === '1')) {
                  e.preventDefault()
                  const ta = e.currentTarget
                  const { selectionStart: a, selectionEnd: b } = ta
                  const next = ta.value.slice(0, a) + '  ' + ta.value.slice(b)
                  setSource(next)
                  requestAnimationFrame(() => ta.setSelectionRange(a + 2, a + 2))
                } else if (e.key === 'Escape') {
                  e.currentTarget.dataset.escaped = '1'
                } else {
                  delete e.currentTarget.dataset.escaped
                }
              }}
            />
          </div>
          <p className="latex_mcp__meta">
            {lineCount} lines. Tab indents; press Escape then Tab to leave the editor.
          </p>

          <div className="latex_mcp__go">
            <PayButton
              label={compileLabel(props.payLabel)}
              runningLabel="Compiling. Waiting for the wallet and pdflatex"
              running={running}
              disabled={!canRun || listing.online === false || !source.trim()}
              onClick={() => {
                setFocusLine(null)
                run({ tool: TOOL, args: { latex_string: source } })
              }}
            />
            <p className="latex_mcp__note">You pay only if the document compiles.</p>
          </div>
        </section>

        <section className="latex_mcp__page" aria-labelledby="latex_mcp-out" aria-busy={running}>
          <h2 id="latex_mcp-out" className="latex_mcp__h">
            PDF
          </h2>

          {!done && !running && (
            <div className="latex_mcp__blank">
              <p>Compile the source and the typeset pages appear here.</p>
            </div>
          )}
          {running && (
            <div className="latex_mcp__blank" role="status">
              <p>Typesetting with pdflatex</p>
            </div>
          )}

          {pdfPath && (
            <>
              <iframe className="latex_mcp__pdf" src={getFileUrl(pdfPath)} title="Compiled PDF" />
              <p className="latex_mcp__links">
                <a href={getFileUrl(pdfPath)} target="_blank" rel="noopener noreferrer">
                  Open in a new tab
                </a>
                <a href={getFileUrl(pdfPath)} download="document.pdf">
                  Download PDF
                </a>
              </p>
            </>
          )}

          {failed && (
            <div className="latex_mcp__problems" data-testid="latex-problems">
              <h3 className="latex_mcp__h3">
                {problems.length === 0
                  ? 'The document did not compile'
                  : problems.length === 1
                    ? 'One problem stopped the PDF'
                    : `${problems.length} problems stopped the PDF`}
              </h3>
              {problems.length > 0 ? (
                <ul className="latex_mcp__plist">
                  {problems.map((p, i) => (
                    <li key={i}>
                      {p.line !== null ? (
                        <button type="button" className="latex_mcp__pjump" onClick={() => goToLine(p.line as number)}>
                          <span className="latex_mcp__pline">Line {p.line}</span>
                          <span>{p.message}</span>
                        </button>
                      ) : (
                        <span className="latex_mcp__pnoline">{p.message}</span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Read the compile log below for the reason.</p>
              )}
            </div>
          )}

          {done && <RawOutput text={text} title={failed ? 'Compile log' : 'Response'} />}
        </section>
      </div>
    </div>
  )
}

export default LatexDesk
