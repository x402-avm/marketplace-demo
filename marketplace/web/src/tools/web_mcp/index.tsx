import React, { useId, useState } from 'react'
import { PayButton, RawOutput, getFileUrl, parseJson } from '../kit'
import type { ToolUIProps } from '../kit'
import './web.css'

export const domain = 'web_mcp'

type ModeId = 'open' | 'info' | 'shot' | 'click' | 'search' | 'api'

const MODES: { id: ModeId; tool: string; name: string; what: string }[] = [
  { id: 'open', tool: 'web_open_page', name: 'Open page', what: 'Load an address in the vendor’s browser.' },
  { id: 'info', tool: 'web_page_info', name: 'Page info', what: 'Read the title, the text and the links of the page at this address.' },
  { id: 'shot', tool: 'web_screen_shoot', name: 'Screenshot', what: 'Take a picture of the page at this address.' },
  { id: 'click', tool: 'web_click_button', name: 'Click', what: 'Open this address and press a button or link on it, picked by its CSS selector.' },
  { id: 'search', tool: 'ddg_search', name: 'Search', what: 'Search the web and get a list of links.' },
  { id: 'api', tool: 'send_api_request', name: 'API request', what: 'Send an HTTP request and read the raw answer.' },
]
const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
const BODY_METHODS = ['POST', 'PUT', 'PATCH']

function host(u: string): string {
  try {
    return new URL(u).host
  } catch {
    return u
  }
}

function normalizeUrl(raw: string): string {
  const t = raw.trim()
  if (!t) return ''
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(t) ? t : `https://${t}`
}

function validJson(s: string): boolean {
  if (!s.trim()) return true
  try {
    const v = JSON.parse(s)
    return typeof v === 'object' && v !== null && !Array.isArray(v)
  } catch {
    return false
  }
}

function explainError(text: string, mode: ModeId): { title: string; body: string } {
  if (/blocked private address/i.test(text)) {
    return { title: 'That address is private', body: 'The vendor’s browser will not open addresses on a private network, such as localhost or 192.168.x.x. Use a public address.' }
  }
  if (/path not allowed/i.test(text)) return { title: 'That file name is not allowed', body: 'Screenshots are saved by the vendor, so the name must not point to a folder.' }
  if (/error parsing json/i.test(text)) return { title: 'Headers or body are not valid JSON', body: 'Both must be a JSON object such as {"Accept": "application/json"}.' }
  if (mode === 'click' && /connection error/i.test(text)) {
    return { title: 'The click did not go through', body: 'Either the page could not be reached or nothing on it matched the selector. Check Page info for the links that exist, then try again.' }
  }
  if (/connection error/i.test(text)) return { title: 'The vendor’s browser did not answer', body: 'The service could not be reached. Try again shortly or use another vendor.' }
  if (mode === 'click' && /timeout|waiting for|selector/i.test(text)) {
    return { title: 'No element matched that selector', body: 'Read Page info to see which links and buttons exist on the page, then try a selector such as a, button or #submit.' }
  }
  if (/timeout|net::|ERR_/i.test(text)) return { title: 'The page did not load', body: 'The site did not respond in time or the address does not exist. Check the spelling and try again.' }
  return { title: 'The service returned an error', body: 'Its own message is shown below.' }
}

/* ---------- result views ---------- */

const Facts: React.FC<{ rows: [string, React.ReactNode][] }> = ({ rows }) => (
  <dl className="web_mcp__facts">
    {rows.map(([k, v]) => (
      <div key={k}>
        <dt>{k}</dt>
        <dd>{v}</dd>
      </div>
    ))}
  </dl>
)

const InfoView: React.FC<{ data: any }> = ({ data }) => {
  const els: { text?: string; href?: string; tag?: string }[] = Array.isArray(data.interactive_elements) ? data.interactive_elements : []
  const blank = !data.url || data.url === 'about:blank'
  if (blank) {
    return (
      <div className="web_mcp__blank">
        <p className="web_mcp__blanktitle">The page came back empty</p>
        <p>The page came back empty. Check the address above and run it again.</p>
      </div>
    )
  }
  return (
    <div className="web_mcp__info">
      <h3 className="web_mcp__pagetitle">{data.title || 'This page has no title'}</h3>
      <p className="web_mcp__pageurl">{data.url}</p>
      <Facts rows={[['Text on the page', `${Number(data.text_length ?? 0).toLocaleString()} characters`], ['Links and buttons found', String(els.length)]]} />
      {data.excerpt && (
        <figure className="web_mcp__excerpt">
          <figcaption>Start of the page text</figcaption>
          <blockquote>{String(data.excerpt).trim()}</blockquote>
        </figure>
      )}
      {els.length > 0 && (
        <div>
          <p className="web_mcp__sub">Links and buttons you can click</p>
          <ul className="web_mcp__els">
            {els.map((el, i) => (
              <li key={i}>
                <span className="web_mcp__tag">{el.tag === 'a' ? 'link' : el.tag}</span>
                <span className="web_mcp__eltext">{el.text}</span>
                {el.href && <span className="web_mcp__elhref">{el.href}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

const SearchView: React.FC<{ data: any; query: string }> = ({ data, query }) => {
  const results: { title?: string; href?: string; body?: string }[] = Array.isArray(data.results) ? data.results : []
  if (!results.length) return <p className="web_mcp__blank">No results for “{query}”. Try other words.</p>
  return (
    <div>
      <p className="web_mcp__sub">
        {results.length === 1 ? 'One result' : `${results.length} results`} for “{query}”
      </p>
      <ol className="web_mcp__hits">
        {results.map((r, i) => (
          <li key={i}>
            <p className="web_mcp__hithost">{r.href ? host(r.href) : ''}</p>
            <h3>
              {r.href ? (
                <a href={r.href} target="_blank" rel="noreferrer">
                  {r.title || r.href}
                </a>
              ) : (
                r.title
              )}
            </h3>
            {r.body && <p className="web_mcp__hitbody">{r.body}</p>}
          </li>
        ))}
      </ol>
    </div>
  )
}

const ApiView: React.FC<{ data: any; url: string; method: string }> = ({ data, url, method }) => {
  const status = Number(data.status_code)
  const kind = status >= 500 ? 'server' : status >= 400 ? 'client' : status >= 300 ? 'redirect' : 'ok'
  const meaning: Record<string, string> = {
    ok: 'The request worked.',
    redirect: 'The address points somewhere else.',
    client: 'The server rejected the request.',
    server: 'The server failed to handle the request.',
  }
  const raw = typeof data.content === 'string' ? data.content : JSON.stringify(data.content ?? '', null, 2)
  let body = raw
  let isJson = false
  try {
    body = JSON.stringify(JSON.parse(raw), null, 2)
    isJson = true
  } catch {
    /* plain text or html */
  }
  const headers = data.headers && typeof data.headers === 'object' ? Object.entries<any>(data.headers) : []
  return (
    <div className="web_mcp__api">
      <div className={`web_mcp__status is-${kind}`}>
        <span className="web_mcp__code">{Number.isFinite(status) ? status : '?'}</span>
        <span>
          {meaning[kind]} <span className="web_mcp__muted">{method} {host(url)}</span>
        </span>
      </div>
      {headers.length > 0 && (
        <details className="web_mcp__hdrs" open>
          <summary>Response headers ({headers.length})</summary>
          <dl className="web_mcp__facts">
            {headers.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{String(v)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
      <p className="web_mcp__sub">{isJson ? 'Body, formatted as JSON' : 'Body'}</p>
      <pre className="web_mcp__body" tabIndex={0}>
        {body.length > 20000 ? body.slice(0, 20000) + '\n(shortened, the full text is in the response below)' : body || '(empty)'}
      </pre>
    </div>
  )
}

/* ---------- the browser ---------- */

const WebBrowser: React.FC<ToolUIProps> = (p) => {
  const uid = useId()
  const [mode, setMode] = useState<ModeId>('open')
  const [address, setAddress] = useState('')
  const [query, setQuery] = useState('')
  const [count, setCount] = useState(5)
  const [selector, setSelector] = useState('')
  const [fullPage, setFullPage] = useState(false)
  const [scrollTo, setScrollTo] = useState('')
  const [method, setMethod] = useState('GET')
  const [headers, setHeaders] = useState('{\n  "Accept": "application/json"\n}')
  const [body, setBody] = useState('{}')
  const [sent, setSent] = useState<{ mode: ModeId; url: string; query: string; method: string }>({ mode: 'open', url: '', query: '', method: 'GET' })
  const [callTime, setCallTime] = useState<number>(() => Date.now())

  React.useEffect(() => {
    if (p.result) {
      setCallTime(Date.now())
    }
  }, [p.result])

  const m = MODES.find((x) => x.id === mode)!
  const url = normalizeUrl(address)
  const hasBody = BODY_METHODS.includes(method)
  const withPass = p.payLabel.startsWith('Run with')
  const verb: Record<ModeId, string> = { open: 'open the page', info: 'read the page', shot: 'take the screenshot', click: 'click', search: 'search', api: `send the ${method} request` }
  const label = withPass ? `${m.name} with your pass` : `Pay ${p.priceOf(m.tool)} and ${verb[mode]}`

  const argsOk: Record<ModeId, boolean> = {
    open: Boolean(url),
    info: Boolean(url),
    shot: Boolean(url),
    click: Boolean(url) && Boolean(selector.trim()),
    search: Boolean(query.trim()),
    api: Boolean(url) && validJson(headers) && (!hasBody || validJson(body)),
  }
  const jsonProblem = mode === 'api' && (!validJson(headers) ? 'Headers' : hasBody && !validJson(body) ? 'Body' : '')

  const go = () => {
    if (p.running || !p.canRun || !argsOk[mode]) return
    setSent({ mode, url, query: query.trim(), method })
    setCallTime(Date.now())
    const args: Record<ModeId, Record<string, any>> = {
      open: { url },
      // each paid call is its own browser session, so the page tools open the address themselves
      info: { url },
      shot: { url, full_page: fullPage, ...(scrollTo.trim() ? { scroll_to_selector: scrollTo.trim() } : {}) },
      click: { url, selector: selector.trim() },
      search: { query: query.trim(), max_results: count },
      api: { url, method, headers: headers.trim() || '{}', data: hasBody ? body.trim() || '{}' : '{}' },
    }
    p.run({ tool: m.tool, args: args[mode] })
  }

  const here = p.result && p.resultTool === m.tool
  const elsewhere = p.result && !here ? MODES.find((x) => x.tool === p.resultTool) : null
  const ok = here && !p.result?.isError
  const data = ok && mode !== 'shot' && mode !== 'open' && mode !== 'click' ? parseJson(p.text) : null
  const problem = here && p.result?.isError ? explainError(p.text, mode) : null
  const shotPath = ok && mode === 'shot' ? p.files.find((f) => /\.(png|jpe?g|webp)$/i.test(f)) : undefined
  const shotUrl = shotPath ? `${getFileUrl(shotPath)}&t=${callTime}` : ''
  const tabId = (id: string) => `${uid}-tab-${id}`

  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    e.preventDefault()
    const next = MODES[(i + step + MODES.length) % MODES.length]
    setMode(next.id)
    document.getElementById(tabId(next.id))?.focus()
  }

  return (
    <div className="web_mcp">
      <div className="web_mcp__window">
        <div className="web_mcp__tabs" role="tablist" aria-label="What to do with the browser">
          {MODES.map((x, i) => (
            <button
              key={x.id}
              id={tabId(x.id)}
              type="button"
              role="tab"
              aria-selected={mode === x.id}
              aria-controls={`${uid}-panel`}
              tabIndex={mode === x.id ? 0 : -1}
              className="web_mcp__tab"
              onClick={() => setMode(x.id)}
              onKeyDown={(e) => onTabKey(e, i)}
            >
              <span>{x.name}</span>
              <span className="web_mcp__price">{p.priceOf(x.tool)}</span>
            </button>
          ))}
        </div>

        <form
          id={`${uid}-panel`}
          role="tabpanel"
          aria-labelledby={tabId(mode)}
          className="web_mcp__chrome"
          onSubmit={(e) => {
            e.preventDefault()
            go()
          }}
        >
          <p className="web_mcp__what">{m.what}</p>

          {mode !== 'search' && (
            <div className="web_mcp__addressrow">
              {mode === 'api' && (
                <select className="web_mcp__method" aria-label="Method" data-testid="field-method" value={method} disabled={p.running} onChange={(e) => setMethod(e.target.value)}>
                  {METHODS.map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              )}
              <input
                className="web_mcp__address"
                type="text"
                inputMode="url"
                aria-label={mode === 'api' ? 'Request address' : 'Web address'}
                data-testid="field-url"
                value={address}
                placeholder={mode === 'api' ? 'https://api.example.com/items' : 'example.com'}
                disabled={p.running}
                spellCheck={false}
                autoCapitalize="off"
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
          )}

          {mode === 'search' && (
            <div className="web_mcp__addressrow">
              <input className="web_mcp__address" type="search" aria-label="Search the web" data-testid="field-query" value={query} placeholder="What do you want to find?" disabled={p.running} onChange={(e) => setQuery(e.target.value)} />
              <label className="web_mcp__count">
                <span>Results</span>
                <input type="number" min={1} max={20} data-testid="field-max_results" value={count} disabled={p.running} onChange={(e) => setCount(Math.min(20, Math.max(1, Math.round(Number(e.target.value)) || 1)))} />
              </label>
            </div>
          )}

          {mode === 'click' && (
            <div className="web_mcp__addressrow">
              <input className="web_mcp__address web_mcp__selector" type="text" aria-label="CSS selector" data-testid="field-selector" value={selector} placeholder="a, button, #submit, .menu-item" disabled={p.running} spellCheck={false} autoCapitalize="off" onChange={(e) => setSelector(e.target.value)} />
            </div>
          )}

          {mode === 'shot' && (
            <div className="web_mcp__opts">
              <label className="web_mcp__check">
                <input type="checkbox" data-testid="field-full_page" checked={fullPage} disabled={p.running} onChange={(e) => setFullPage(e.target.checked)} />
                <span>Whole page, not only what fits on the screen</span>
              </label>
              <label className="web_mcp__field">
                <span>Scroll to this element first (optional)</span>
                <input type="text" data-testid="field-scroll_to_selector" value={scrollTo} placeholder="#pricing" disabled={p.running} spellCheck={false} onChange={(e) => setScrollTo(e.target.value)} />
              </label>
            </div>
          )}

          {mode === 'api' && (
            <div className="web_mcp__builder">
              <label className="web_mcp__field">
                <span>Headers, as a JSON object</span>
                <textarea data-testid="field-headers" rows={4} value={headers} disabled={p.running} spellCheck={false} onChange={(e) => setHeaders(e.target.value)} aria-invalid={!validJson(headers)} />
              </label>
              {hasBody ? (
                <label className="web_mcp__field">
                  <span>Body, as a JSON object</span>
                  <textarea data-testid="field-data" rows={4} value={body} disabled={p.running} spellCheck={false} onChange={(e) => setBody(e.target.value)} aria-invalid={!validJson(body)} />
                </label>
              ) : (
                <p className="web_mcp__nobody">{method} requests carry no body. Choose POST, PUT or PATCH to send one.</p>
              )}
              {jsonProblem && <p className="web_mcp__warn">{jsonProblem} is not a valid JSON object yet.</p>}
            </div>
          )}

          {(mode === 'info' || mode === 'shot' || mode === 'click') && (
            <p className="web_mcp__session">The vendor’s browser opens the address above and works on it in the same call.</p>
          )}

          <div className="web_mcp__go">
            <PayButton label={label} running={p.running} runningLabel={`Working in the vendor’s browser`} disabled={!p.canRun || !argsOk[mode]} onClick={go} />
          </div>
        </form>

        <div className="web_mcp__viewport" aria-live="polite">
          {!here && !p.running && (
            <div className="web_mcp__idle">
              <p>{elsewhere ? `The last call was ${elsewhere.name}. Run ${m.name} to see its result here.` : 'Nothing has been loaded yet. The result of each action appears here.'}</p>
            </div>
          )}
          {p.running && <p className="web_mcp__idle">Waiting for the vendor’s browser</p>}

          {problem && (
            <div className="web_mcp__refused" data-testid="web-explain">
              <p className="web_mcp__refusedtitle">{problem.title}</p>
              <p>{problem.body}</p>
            </div>
          )}

          {ok && mode === 'open' && (
            <div className="web_mcp__opened">
              <p className="web_mcp__sub">Loaded</p>
              <p className="web_mcp__pagetitle">{host(sent.url || p.text.replace(/^Opened\s+/, ''))}</p>
              <p className="web_mcp__pageurl">{p.text.replace(/^Opened\s+/, '')}</p>
              <p className="web_mcp__next">
                Next, read it with{' '}
                <button type="button" className="web_mcp__link" onClick={() => setMode('info')}>
                  Page info
                </button>{' '}
                or{' '}
                <button type="button" className="web_mcp__link" onClick={() => setMode('shot')}>
                  Screenshot
                </button>
                .
              </p>
            </div>
          )}

          {ok && mode === 'click' && (
            <div className="web_mcp__opened">
              <p className="web_mcp__sub">Clicked</p>
              <p className="web_mcp__pagetitle">{p.text.replace(/^Successfully clicked\s*/, '') || selector}</p>
              <p className="web_mcp__next">The page waited for the click to finish loading. Run Page info to see what changed.</p>
            </div>
          )}

          {ok && mode === 'info' && data && <InfoView data={data} />}
          {ok && mode === 'search' && data && <SearchView data={data as any} query={sent.query} />}
          {ok && mode === 'api' && data && <ApiView data={data} url={sent.url} method={sent.method} />}

          {ok && mode === 'shot' && (
            <div className="web_mcp__shotwrap">
              {shotPath ? (
                <figure className="web_mcp__device">
                  <div className="web_mcp__devicebar" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </div>
                  <div className="web_mcp__screen">
                    <img src={shotUrl} alt="Screenshot of the page the vendor’s browser had open" />
                  </div>
                  <figcaption>
                    <a href={shotUrl} target="_blank" rel="noreferrer">
                      Open the image in full size
                    </a>
                  </figcaption>
                </figure>
              ) : (
                <p className="web_mcp__blank">The service did not name an image file. Its message is shown below.</p>
              )}
            </div>
          )}
        </div>
      </div>

      {p.result && <RawOutput text={p.text} title="What the service sent back" />}
    </div>
  )
}

export default WebBrowser
