import React, { useRef, useState } from 'react'
import { PayButton, RawOutput } from '../kit'
import type { ToolUIProps } from '../kit'
import './sandbox.css'

export const domain = 'sandbox_mcp'

const TOOL = 'run_sandbox_code'
const INDENT = '    '

const LANGS: { id: string; name: string; starter: string }[] = [
  {
    id: 'python',
    name: 'Python',
    starter: `# Count the words in a sentence, most common first
from collections import Counter

text = "the quick brown fox jumps over the lazy dog the end"
for word, n in Counter(text.split()).most_common(3):
    print(f"{word}: {n}")
`,
  },
  {
    id: 'javascript',
    name: 'JavaScript',
    starter: `// First ten Fibonacci numbers
const fib = [0, 1]
while (fib.length < 10) fib.push(fib.at(-1) + fib.at(-2))
console.log(fib.join(', '))
`,
  },
  {
    id: 'c',
    name: 'C',
    starter: `#include <stdio.h>

int main(void) {
    for (int i = 1; i <= 5; i++) {
        printf("%d squared is %d\\n", i, i * i);
    }
    return 0;
}
`,
  },
  {
    id: 'cpp',
    name: 'C++',
    starter: `#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v{5, 3, 9, 1, 7};
    std::sort(v.begin(), v.end());
    for (int x : v) std::cout << x << ' ';
    std::cout << std::endl;
}
`,
  },
  {
    id: 'java',
    name: 'Java',
    starter: `public class Main {
    public static void main(String[] args) {
        StringBuilder s = new StringBuilder("sandbox");
        System.out.println(s.reverse());
    }
}
`,
  },
]

const STARTERS = new Set(LANGS.map((l) => l.starter))

/** The service answers "Stdout:\n...\nStderr:\n..." when the code ran. */
function splitStreams(text: string): { stdout: string; stderr: string } | null {
  const m = text.match(/^Stdout:\n([\s\S]*?)\nStderr:\n([\s\S]*)$/)
  return m ? { stdout: m[1], stderr: m[2] } : null
}

function explainError(text: string, lang: string, supported: boolean): { title: string; body: string } {
  const unsupported = !supported || /unsupported language/i.test(text)
  if (/isolation unavailable/i.test(text)) {
    return {
      title: 'Nothing ran: this vendor cannot isolate code right now',
      body:
        'The sandbox refuses to run anything unless it can lock the program away from the vendor’s machine, and that protection is switched off on the server at the moment. This is a problem on the vendor’s side, not in your code.' +
        (unsupported ? ` Separately, “${lang}” is not a language this sandbox runs.` : ''),
    }
  }
  if (unsupported) {
    return {
      title: `“${lang || 'nothing'}” is not a language this sandbox runs`,
      body: `Choose Python, JavaScript, C, C++ or Java and run again.`,
    }
  }
  if (/connecting to runtime|connection/i.test(text)) {
    return { title: 'The sandbox did not answer', body: 'The vendor’s code runner is not reachable. Try again shortly or use another vendor.' }
  }
  if (/timed? ?out/i.test(text)) {
    return { title: 'Your program ran too long', body: 'Programs are stopped after 5 seconds. Look for a loop that never ends or a wait for input.' }
  }
  return { title: 'The sandbox returned an error', body: 'The service’s own message is shown below.' }
}

const Editor: React.FC<{ value: string; onChange: (v: string) => void; disabled: boolean; label: string }> = ({ value, onChange, disabled, label }) => {
  const ref = useRef<HTMLTextAreaElement>(null)
  const gutter = useRef<HTMLDivElement>(null)
  const escaped = useRef(false)
  const lines = Math.max(1, value.split('\n').length)

  const replace = (start: number, end: number, insert: string, caret: number) => {
    const el = ref.current!
    onChange(value.slice(0, start) + insert + value.slice(end))
    requestAnimationFrame(() => {
      el.selectionStart = el.selectionEnd = caret
    })
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape') {
      escaped.current = true
      return
    }
    if (e.key !== 'Tab') {
      escaped.current = false
      return
    }
    if (escaped.current) {
      // Esc, then Tab: leave the editor like any other field.
      escaped.current = false
      return
    }
    e.preventDefault()
    const el = e.currentTarget
    const { selectionStart: s, selectionEnd: t } = el
    const lineStart = value.lastIndexOf('\n', s - 1) + 1
    if (e.shiftKey) {
      const head = value.slice(lineStart, lineStart + INDENT.length)
      const cut = head.length - head.trimStart().length
      if (cut > 0) replace(lineStart, lineStart + Math.min(cut, INDENT.length), '', Math.max(lineStart, s - Math.min(cut, INDENT.length)))
      return
    }
    if (s !== t && value.slice(s, t).includes('\n')) {
      const block = value.slice(lineStart, t)
      const indented = block.replace(/^/gm, INDENT)
      replace(lineStart, t, indented, t + (indented.length - block.length))
      return
    }
    replace(s, t, INDENT, s + INDENT.length)
  }

  return (
    <div className={`sandbox_mcp__editor${disabled ? ' is-disabled' : ''}`}>
      <div className="sandbox_mcp__gutter" ref={gutter} aria-hidden="true">
        {Array.from({ length: lines }, (_, i) => (
          <span key={i}>{i + 1}</span>
        ))}
      </div>
      <textarea
        ref={ref}
        className="sandbox_mcp__code"
        data-testid="field-code"
        aria-label={label}
        aria-describedby="sandbox-keys"
        value={value}
        disabled={disabled}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        wrap="off"
        rows={Math.min(22, Math.max(12, lines + 1))}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onScroll={(e) => {
          if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop
        }}
      />
    </div>
  )
}

const CodeSandbox: React.FC<ToolUIProps> = (p) => {
  const language: string = p.args.language ?? 'python'
  const code: string = p.args.code ?? LANGS[0].starter
  const lang = LANGS.find((l) => l.id === language.trim().toLowerCase())
  const supported = Boolean(lang)
  const [ranLang, setRanLang] = useState(language)

  const set = (patch: Record<string, any>) => p.setArgs({ language, code, ...p.args, ...patch })

  const pick = (id: string) => {
    const next = LANGS.find((l) => l.id === id)!
    // Swap in the new example only when the editor still holds an untouched example.
    if (!code.trim() || STARTERS.has(code)) set({ language: id, code: next.starter })
    else set({ language: id })
  }

  const withPass = p.payLabel.startsWith('Run with')
  const shown = lang?.name ?? (language.trim() || 'the code')
  const label = withPass ? `Run ${shown} with your pass` : `Pay ${p.priceOf(TOOL)} and run ${lang ? `the ${lang.name}` : 'this'} code`
  const run = () => {
    if (p.running) return
    setRanLang(language)
    p.run({ tool: TOOL, args: { code, language: language.trim().toLowerCase() } })
  }

  const showResult = p.result && p.resultTool === TOOL
  const streams = showResult && !p.result?.isError ? splitStreams(p.text) : null
  const problem = showResult && p.result?.isError ? explainError(p.text, ranLang, Boolean(LANGS.find((l) => l.id === ranLang.trim().toLowerCase()))) : null

  return (
    <div className="sandbox_mcp">
      <div className="sandbox_mcp__desk">
        <div className="sandbox_mcp__langbar">
          <div className="sandbox_mcp__seg" role="radiogroup" aria-label="Language">
            {LANGS.map((l) => (
              <button
                key={l.id}
                type="button"
                role="radio"
                aria-checked={lang?.id === l.id}
                className="sandbox_mcp__segbtn"
                disabled={p.running}
                onClick={() => pick(l.id)}
              >
                {l.name}
              </button>
            ))}
          </div>
          <div className="sandbox_mcp__other">
            <label htmlFor="sandbox-language">Language</label>
            <input
              id="sandbox-language"
              data-testid="field-language"
              value={language}
              disabled={p.running}
              spellCheck={false}
              autoCapitalize="off"
              aria-describedby="sandbox-langnote"
              onChange={(e) => set({ language: e.target.value })}
            />
          </div>
        </div>
        <p id="sandbox-langnote" className={`sandbox_mcp__langnote${supported ? '' : ' is-warn'}`}>
          {supported
            ? 'Runs for up to 5 seconds with no network access.' + (lang?.id === 'java' ? ' The class must be called Main.' : '')
            : `“${language.trim() || 'nothing'}” is not on this sandbox’s list (Python, JavaScript, C, C++, Java). The service will refuse it and you will not be charged.`}
        </p>

        <Editor value={code} onChange={(v) => set({ code: v })} disabled={p.running} label={`${lang?.name ?? 'Program'} code`} />

        <div className="sandbox_mcp__foot">
          <p id="sandbox-keys" className="sandbox_mcp__keys">
            Tab indents. Press Esc, then Tab, to move on.
            {lang && code !== lang.starter && (
              <>
                {' '}
                <button type="button" className="sandbox_mcp__reset" disabled={p.running} onClick={() => set({ code: lang.starter })}>
                  Load the {lang.name} example
                </button>
              </>
            )}
          </p>
          <PayButton label={label} running={p.running} runningLabel={`Running your ${lang?.name ?? ''} code`.replace('  ', ' ')} disabled={!p.canRun || !code.trim()} onClick={run} />
        </div>
      </div>

      <section className="sandbox_mcp__console" aria-label="Output" aria-live="polite">
        <div className="sandbox_mcp__consolehead">
          <span>Output</span>
          {streams && <span>{ranLang}</span>}
        </div>
        <div className="sandbox_mcp__screen">
          {!showResult && !p.running && <p className="sandbox_mcp__idle">What your program prints appears here, with errors kept apart from normal output.</p>}
          {p.running && <p className="sandbox_mcp__idle">Running<span className="sandbox_mcp__cursor" aria-hidden="true" /></p>}
          {streams && (
            <>
              <div className="sandbox_mcp__stream">
                <p className="sandbox_mcp__streamname">Standard output</p>
                {streams.stdout.trim() ? <pre>{streams.stdout.replace(/\n$/, '')}</pre> : <p className="sandbox_mcp__nothing">Nothing printed.</p>}
              </div>
              <div className={`sandbox_mcp__stream${streams.stderr.trim() ? ' is-err' : ''}`}>
                <p className="sandbox_mcp__streamname">Errors and warnings</p>
                {streams.stderr.trim() ? <pre>{streams.stderr.replace(/\n$/, '')}</pre> : <p className="sandbox_mcp__nothing">None.</p>}
              </div>
            </>
          )}
          {showResult && !streams && !problem && <pre>{p.text}</pre>}
          {problem && (
            <div className="sandbox_mcp__refused" data-testid="sandbox-explain">
              <p className="sandbox_mcp__refusedtitle">{problem.title}</p>
              <p>{problem.body}</p>
              <p>You were not charged.</p>
            </div>
          )}
        </div>
      </section>

      {showResult && <RawOutput text={p.text} title="What the service sent back" />}
    </div>
  )
}

export default CodeSandbox
