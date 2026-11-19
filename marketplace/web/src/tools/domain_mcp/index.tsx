import React, { useEffect, useRef, useState } from 'react'
import { PayButton, RawOutput, parseJson } from '../kit'
import type { ToolUIProps } from '../kit'
import './domain.css'

export const domain = 'domain_mcp'

type LookupKey = 'domain_whois' | 'domain_dns' | 'domain_ssl' | 'domain_ip'

const LOOKUPS: { tool: LookupKey; tab: string; verb: string; what: string }[] = [
  { tool: 'domain_whois', tab: 'Registration', verb: 'look up the registration', what: 'Who registered the domain, when it was created, when it expires and which name servers answer for it (WHOIS).' },
  { tool: 'domain_dns', tab: 'DNS records', verb: 'look up DNS records', what: 'The addresses, mail servers, name servers and text records the domain publishes.' },
  { tool: 'domain_ssl', tab: 'Certificate', verb: 'check the certificate', what: 'Connects on port 443 and inspects the site’s HTTPS certificate, issuer, validity and alternative names.' },
  { tool: 'domain_ip', tab: 'IP address', verb: 'find the IP address', what: 'The IPv4 address the domain name resolves to right now.' },
]

const DNS_TYPES: Record<string, string> = {
  A: 'IPv4 address',
  AAAA: 'IPv6 address',
  MX: 'Mail server',
  NS: 'Name server',
  TXT: 'Text record',
  CNAME: 'Alias',
}

const STATUS_WORDS: Record<string, string> = {
  clientdeleteprohibited: 'Deletion locked by the registrar',
  clienttransferprohibited: 'Transfer locked by the registrar',
  clientupdateprohibited: 'Changes locked by the registrar',
  serverdeleteprohibited: 'Deletion locked by the registry',
  servertransferprohibited: 'Transfer locked by the registry',
  serverupdateprohibited: 'Changes locked by the registry',
  clienthold: 'On hold by the registrar',
  serverhold: 'On hold by the registry',
  active: 'Active',
  ok: 'Active',
}

/** Accept a pasted URL or address and keep only the host name. */
function cleanDomain(raw: string): string {
  let d = raw.trim().toLowerCase()
  d = d.replace(/^[a-z]+:\/\//, '')
  d = d.split(/[/?#]/)[0]
  d = d.replace(/:\d+$/, '').replace(/\.$/, '')
  return d
}

function unwrap(text: string): any {
  const outer = parseJson<any>(text)
  if (outer && typeof outer === 'object' && 'result' in outer) {
    const r = outer.result
    if (typeof r === 'string') return parseJson(r) ?? r
    return r
  }
  return outer ?? text
}

function toDate(v: any): Date | null {
  const s = Array.isArray(v) ? v[0] : v
  if (!s || typeof s !== 'string') return null
  const d = new Date(/^\d{4}-\d{2}-\d{2} /.test(s) ? s.replace(' ', 'T') : s)
  return Number.isNaN(d.getTime()) ? null : d
}

const fmt = (d: Date) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
const DAY = 86_400_000

function span(from: Date, to: Date): string {
  const days = Math.round(Math.abs(to.getTime() - from.getTime()) / DAY)
  if (days < 60) return days === 1 ? '1 day' : `${days} days`
  const months = Math.round(days / 30.44)
  if (months < 24) return `${months} months`
  const years = Math.floor(months / 12)
  const rest = months % 12
  return rest ? `${years} years and ${rest} month${rest === 1 ? '' : 's'}` : `${years} years`
}

function explainError(text: string, d: string): string {
  if (/not known|nxdomain|no address|name or service/i.test(text)) return `${d} does not resolve. Check the spelling; the name may not be registered.`
  if (/timed out|timeout/i.test(text)) return `${d} did not answer in time. The server may be down or block outside connections.`
  if (/refused/i.test(text)) return `${d} refused the connection. The site may not serve HTTPS.`
  if (/certificate|ssl/i.test(text)) return `The certificate for ${d} could not be verified. It may be expired, self-signed or issued for another name.`
  if (/connection error/i.test(text)) return 'The lookup service did not answer. Try again in a moment.'
  return `The lookup for ${d} did not finish. The service’s own message is below.`
}

/* ---------- result views ---------- */

const Fact: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="domain_mcp__fact">
    <dt>{label}</dt>
    <dd>{children}</dd>
  </div>
)

const WhoisView: React.FC<{ data: any }> = ({ data }) => {
  if (!data || typeof data !== 'object') return <pre className="domain_mcp__plain">{String(data)}</pre>
  const now = new Date()
  const created = toDate(data.creation_date)
  const expires = toDate(data.expiration_date)
  const updated = toDate(data.updated_date)
  const ns: string[] = Array.from(new Set(([] as string[]).concat(data.name_servers ?? []).map((s) => String(s).toLowerCase())))
  const statuses: string[] = Array.from(
    new Set(
      ([] as string[])
        .concat(data.status ?? [])
        .map((s) => String(s).split(/\s+/)[0])
        .map((s) => STATUS_WORDS[s.toLowerCase()] ?? s),
    ),
  )
  const where = [data.city, data.state, data.country].filter(Boolean).join(', ')
  const emails = ([] as string[]).concat(data.emails ?? [])
  return (
    <div className="domain_mcp__whois">
      <p className="domain_mcp__headline">{String(data.domain_name ?? '').toLowerCase() || 'Registration record'}</p>
      <dl className="domain_mcp__facts">
        <Fact label="Registrar">
          {data.registrar ? (
            data.registrar_url ? (
              <a href={String(data.registrar_url).startsWith('http') ? data.registrar_url : `https://${data.registrar_url}`} target="_blank" rel="noreferrer">
                {data.registrar}
              </a>
            ) : (
              data.registrar
            )
          ) : (
            'Not published'
          )}
        </Fact>
        <Fact label="Registered">{created ? <>{fmt(created)} <span className="domain_mcp__aside">{span(created, now)} ago</span></> : 'Not published'}</Fact>
        <Fact label="Expires">
          {expires ? (
            <>
              {fmt(expires)}{' '}
              <span className="domain_mcp__aside">{expires > now ? `in ${span(now, expires)}` : `${span(expires, now)} ago`}</span>
            </>
          ) : (
            'Not published'
          )}
        </Fact>
        {updated && <Fact label="Last changed">{fmt(updated)}</Fact>}
        {where && <Fact label="Registrant location">{where}</Fact>}
        {data.dnssec && <Fact label="DNSSEC">{String(data.dnssec)}</Fact>}
        {emails.length > 0 && <Fact label="Abuse contact">{emails.join(', ')}</Fact>}
      </dl>
      {ns.length > 0 && (
        <div className="domain_mcp__group">
          <h4>Name servers</h4>
          <ul className="domain_mcp__mono-list">
            {ns.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      )}
      {statuses.length > 0 && (
        <div className="domain_mcp__group">
          <h4>Status</h4>
          <ul className="domain_mcp__tags">
            {statuses.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

const DnsView: React.FC<{ data: any }> = ({ data }) => {
  if (!data || typeof data !== 'object') return <pre className="domain_mcp__plain">{String(data)}</pre>
  const order = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT']
  const types = Object.keys(data).sort((a, b) => (order.indexOf(a) + 99) % 99 - (order.indexOf(b) + 99) % 99)
  const missing = ['A', 'AAAA', 'MX', 'NS', 'TXT'].filter((t) => !data[t] || data[t].length === 0)
  if (types.length === 0) return <p className="domain_mcp__note">The domain publishes no A, AAAA, MX, NS or TXT records.</p>
  return (
    <div className="domain_mcp__dns">
      <div className="domain_mcp__tablewrap">
        <table className="domain_mcp__table">
          <caption className="domain_mcp__sr">DNS records by type</caption>
          <thead>
            <tr>
              <th scope="col">Type</th>
              <th scope="col">Value</th>
            </tr>
          </thead>
          {types.map((t) => {
            const rows: string[] = ([] as string[]).concat(data[t] ?? [])
            return (
              <tbody key={t} className="domain_mcp__rtype">
                {rows.map((v, i) => {
                  let value: React.ReactNode = v
                  if (t === 'MX') {
                    const [pri, ...host] = v.split(' ')
                    value = (
                      <>
                        {host.join(' ')} <span className="domain_mcp__aside">priority {pri}</span>
                      </>
                    )
                  } else if (t === 'TXT') {
                    value = v.replace(/^"|"$/g, '').replace(/" "/g, '')
                  }
                  return (
                    <tr key={i}>
                      {i === 0 ? (
                        <th scope="rowgroup" rowSpan={rows.length}>
                          <span className="domain_mcp__type">{t}</span>
                          <span className="domain_mcp__typename">
                            {DNS_TYPES[t] ?? 'Record'}
                            {rows.length > 1 ? `, ${rows.length}` : ''}
                          </span>
                        </th>
                      ) : null}
                      <td>{value}</td>
                    </tr>
                  )
                })}
              </tbody>
            )
          })}
        </table>
      </div>
      {missing.length > 0 && <p className="domain_mcp__note">No {missing.join(' or ')} records{missing.includes('AAAA') ? '; the domain has no IPv6 address' : ''}.</p>}
    </div>
  )
}

const renderEntity = (ent: any) => {
  if (!ent) return null
  if (typeof ent === 'string') return ent
  const cn = ent.CN ?? ent.cn
  const o = ent.O ?? ent.o
  if (cn && o) {
    return (
      <>
        {cn} <span className="domain_mcp__aside">({o})</span>
      </>
    )
  }
  return cn || o || JSON.stringify(ent)
}

const CertView: React.FC<{ data: any; host: string }> = ({ data, host }) => {
  const now = new Date()
  const obj = data && typeof data === 'object' ? data : null
  const end = toDate(obj ? obj.notAfter ?? obj.not_after ?? obj.expires : data)
  const start = obj ? toDate(obj.notBefore ?? obj.not_before) : null
  if (!end) return <pre className="domain_mcp__plain">{typeof data === 'string' ? data : JSON.stringify(data, null, 2)}</pre>
  const daysLeft = typeof obj?.days_left === 'number' ? obj.days_left : Math.floor((end.getTime() - now.getTime()) / DAY)
  const state = daysLeft < 0 ? 'expired' : daysLeft <= 14 ? 'urgent' : daysLeft <= 30 ? 'soon' : 'fine'
  // With a start date the bar runs start to expiry; without one it shows the next twelve months.
  const from = start ?? now
  const to = start ? end : new Date(now.getTime() + 365 * DAY)
  const pct = (d: Date) => Math.min(100, Math.max(0, ((d.getTime() - from.getTime()) / (to.getTime() - from.getTime())) * 100))
  const ticks = start
    ? []
    : Array.from({ length: 4 }, (_, i) => {
        const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + (i + 1) * 3, 1))
        return { d, left: pct(d) }
      })
  const issuer = obj?.issuer
  const subject = obj?.subject
  const tlsVersion = obj?.tls_version ?? obj?.tlsVersion
  const serialNumber = obj?.serial_number ?? obj?.serialNumber
  const san: string[] = obj?.subjectAltName ?? obj?.san ?? []
  return (
    <div className={`domain_mcp__cert is-${state}`}>
      <p className="domain_mcp__headline">
        {daysLeft < 0 ? `Expired ${-daysLeft} days ago` : daysLeft === 0 ? 'Expires today' : `${daysLeft} days left`}
      </p>
      <p className="domain_mcp__certline">
        The certificate for {host} {daysLeft < 0 ? 'expired on' : 'is valid until'} {fmt(end)}.
        {state === 'urgent' && ' Renew it now; browsers will warn visitors once it lapses.'}
        {state === 'soon' && ' Renewal is due within a month.'}
      </p>
      <div className="domain_mcp__timeline" role="img" aria-label={start ? `Valid from ${fmt(start)} to ${fmt(end)}, ${daysLeft} days left` : `${daysLeft} days from today until expiry`}>
        <div className="domain_mcp__track">
          {start ? (
            <>
              <span className="domain_mcp__left" style={{ width: '100%' }} />
              <span className="domain_mcp__used" style={{ width: `${pct(now)}%` }} />
              <span className="domain_mcp__now" style={{ left: `${pct(now)}%` }} />
            </>
          ) : (
            <span className="domain_mcp__left" style={{ width: `${pct(end)}%` }} />
          )}
          {ticks.map((t) => (
            <span key={t.left} className="domain_mcp__tick" style={{ left: `${t.left}%` }} />
          ))}
        </div>
        <div className="domain_mcp__scale" aria-hidden="true">
          <span>{start ? `Issued ${fmt(start)}` : 'Today'}</span>
          {!start && end > to && <span>Expiry is beyond this year</span>}
          <span>{start ? `Expires ${fmt(end)}` : fmt(to)}</span>
        </div>
      </div>
      {(issuer || subject || tlsVersion || serialNumber) && (
        <dl className="domain_mcp__facts">
          {subject && <Fact label="Issued to">{renderEntity(subject)}</Fact>}
          {issuer && <Fact label="Issued by">{renderEntity(issuer)}</Fact>}
          {tlsVersion && <Fact label="TLS version">{tlsVersion}</Fact>}
          {serialNumber && (
            <Fact label="Serial number">
              <span className="domain_mcp__mono">{serialNumber}</span>
            </Fact>
          )}
        </dl>
      )}
      {san.length > 0 && (
        <div className="domain_mcp__group">
          <h4>Subject alternative names ({san.length})</h4>
          <ul className="domain_mcp__tags">
            {san.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </div>
      )}
      {!issuer && !subject && !tlsVersion && san.length === 0 && (
        <p className="domain_mcp__note">This service reports the expiry date only, not the issuer or the names on the certificate.</p>
      )}
    </div>
  )
}

const IpView: React.FC<{ data: any; host: string }> = ({ data, host }) => {
  const list: string[] = ([] as any[]).concat(data && typeof data === 'object' && !Array.isArray(data) ? data.ips ?? data.ip ?? [] : data ?? []).map(String)
  const loc = data && typeof data === 'object' && !Array.isArray(data) ? [data.city, data.region, data.country].filter(Boolean).join(', ') : ''
  return (
    <div className="domain_mcp__ip">
      <ul className="domain_mcp__addrs">
        {list.map((ip) => (
          <li key={ip}>
            <span className="domain_mcp__addr">{ip}</span>
            <span className="domain_mcp__aside">{ip.includes(':') ? 'IPv6' : 'IPv4'}</span>
          </li>
        ))}
      </ul>
      <p className="domain_mcp__note">
        {host} points here now. Large sites answer from many addresses; the DNS records lookup lists all of them.
        {loc && ` Located in ${loc}.`}
      </p>
    </div>
  )
}

/* ---------- the panel ---------- */

interface Done {
  host: string
  text: string
  isError: boolean
}

const DomainLookup: React.FC<ToolUIProps> = (p) => {
  const raw: string = p.args.domain ?? ''
  const host = cleanDomain(raw)
  const [active, setActive] = useState<LookupKey>('domain_whois')
  const [done, setDone] = useState<Partial<Record<LookupKey, Done>>>({})
  const pending = useRef<{ tool: LookupKey; host: string } | null>(null)
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  // Keep each lookup's last answer so switching tabs does not lose it.
  useEffect(() => {
    if (!p.result || !p.resultTool || !pending.current || pending.current.tool !== p.resultTool) return
    const { tool, host: h } = pending.current
    setDone((d) => ({ ...d, [tool]: { host: h, text: p.text, isError: Boolean(p.result?.isError) } }))
  }, [p.result, p.resultTool, p.text])

  const withPass = p.payLabel.startsWith('Run with')
  const lookup = LOOKUPS.find((l) => l.tool === active)!
  const label = withPass ? `${lookup.verb[0].toUpperCase()}${lookup.verb.slice(1)} with your pass` : `Pay ${p.priceOf(active)} and ${lookup.verb}`
  const valid = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(host)
  const go = () => {
    if (!valid || p.running) return
    pending.current = { tool: active, host }
    p.run({ tool: active, args: { domain: host } })
  }

  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    const n = LOOKUPS.length
    let j = -1
    if (e.key === 'ArrowRight') j = (i + 1) % n
    else if (e.key === 'ArrowLeft') j = (i - 1 + n) % n
    else if (e.key === 'Home') j = 0
    else if (e.key === 'End') j = n - 1
    if (j < 0) return
    e.preventDefault()
    setActive(LOOKUPS[j].tool)
    tabRefs.current[LOOKUPS[j].tool]?.focus()
  }

  const mine = done[active]
  const stale = mine && mine.host !== host && host
  const data = mine && !mine.isError ? unwrap(mine.text) : null
  const lastHere = p.result && p.resultTool === active && !p.running

  return (
    <div className="domain_mcp">
      <form
        className="domain_mcp__entry"
        onSubmit={(e) => {
          e.preventDefault()
          go()
        }}
      >
        <label htmlFor="domain-input" className="domain_mcp__label">
          Domain
        </label>
        <input
          id="domain-input"
          className="domain_mcp__input"
          data-testid="field-domain"
          value={raw}
          placeholder="example.com"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          inputMode="url"
          disabled={p.running}
          aria-describedby="domain-hint"
          onChange={(e) => p.setArgs({ ...p.args, domain: e.target.value })}
        />
        <p id="domain-hint" className="domain_mcp__hint">
          {raw && !valid
            ? 'Enter a domain name such as example.com, without spaces.'
            : raw && host !== raw.trim()
              ? `Looking up ${host}. The rest of the address is ignored.`
              : 'Each lookup below is paid separately. Pasting a full web address works too.'}
        </p>
      </form>

      <div className="domain_mcp__report">
        <div className="domain_mcp__tabs" role="tablist" aria-label="Lookups">
          {LOOKUPS.map((l, i) => {
            const d = done[l.tool]
            return (
              <button
                key={l.tool}
                ref={(el) => {
                  tabRefs.current[l.tool] = el
                }}
                type="button"
                role="tab"
                id={`domain-tab-${l.tool}`}
                aria-controls="domain-panel"
                aria-selected={active === l.tool}
                tabIndex={active === l.tool ? 0 : -1}
                className="domain_mcp__tab"
                onClick={() => setActive(l.tool)}
                onKeyDown={(e) => onTabKey(e, i)}
              >
                <span className="domain_mcp__tabname">{l.tab}</span>
                <span className="domain_mcp__tabprice">
                  {p.priceOf(l.tool)}
                  {d && <span className="domain_mcp__tabstate">{d.isError ? 'failed' : 'done'}</span>}
                </span>
              </button>
            )
          })}
        </div>

        <div className="domain_mcp__panel" role="tabpanel" id="domain-panel" aria-labelledby={`domain-tab-${active}`}>
          <div className="domain_mcp__ask">
            <p className="domain_mcp__what">{lookup.what}</p>
            <PayButton label={label} running={p.running} runningLabel={`Looking up ${host}`} disabled={!p.canRun || !valid} onClick={go} />
          </div>

          <div className="domain_mcp__answer" aria-live="polite">
            {!mine && !p.running && <p className="domain_mcp__note">{valid ? `Not looked up yet for ${host}.` : 'Enter a domain above to start.'}</p>}
            {mine && stale && <p className="domain_mcp__note">These results are for {mine.host}. Run the lookup again for {host}.</p>}
            {mine?.isError && <p className="domain_mcp__problem">{explainError(mine.text, mine.host)}</p>}
            {data !== null && active === 'domain_whois' && <WhoisView data={data} />}
            {data !== null && active === 'domain_dns' && <DnsView data={data} />}
            {data !== null && active === 'domain_ssl' && <CertView data={data} host={mine!.host} />}
            {data !== null && active === 'domain_ip' && <IpView data={data} host={mine!.host} />}
          </div>
        </div>
      </div>

      {p.result && (
        <RawOutput
          text={p.text}
          title={lastHere ? 'What the service sent back' : `What the service sent back for the last lookup (${LOOKUPS.find((l) => l.tool === p.resultTool)?.tab ?? p.resultTool})`}
        />
      )}
    </div>
  )
}

export default DomainLookup
