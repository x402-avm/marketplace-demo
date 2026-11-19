import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getListings } from '../api'
import type { Listing } from '../types'
import { CATEGORIES, domainInfo } from '../lib/domains'
import { vendorById } from '../lib/vendors'
import { cheapestPrice, fromPrices, groupByDomain, money } from '../lib/catalog'
import { useSettlements } from '../hooks/useChain'
import { ago } from '../components/Shell'
import { resolveAssetName } from '../utils/format'

export const MarketplacePage: React.FC = () => {
  const [listings, setListings] = useState<Listing[]>([])
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    getListings()
      .then(setListings)
      .catch((e) => setError(e.message))
  }, [])

  const byDomain = useMemo(() => groupByDomain(listings), [listings])
  const q = query.trim().toLowerCase()
  const visible = (domain: string) => {
    if (!q) return true
    const d = domainInfo(domain)
    return [d.title, d.summary, domain].some((s) => s.toLowerCase().includes(q))
  }

  return (
    <div className="page home">
      <section className="home__hero">
        <div className="home__lede">
          <h1>Pay for each call. Check every payment on the chain.</h1>
          <p className="home__sub">
            Sixteen AI services from four independent vendors. Choose a vendor, pay per call or buy that vendor's pass,
            then open the transaction in the explorer.
          </p>
        </div>
        <SettledFeed />
      </section>

      <section className="directory" aria-labelledby="directory-title">
        <div className="directory__head">
          <h2 id="directory-title">Directory</h2>
          <label className="directory__search">
            <span className="visually-hidden">Find a service</span>
            <input
              className="input"
              type="search"
              placeholder="Find a service, e.g. speech, pdf, video"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>

        {error && <p className="notice notice--error">The marketplace could not load its services: {error}</p>}
        {!error && listings.length === 0 && <p className="state">Loading services</p>}

        {CATEGORIES.map((cat) => {
          const domains = Object.keys(byDomain)
            .filter((d) => domainInfo(d).category === cat && visible(d))
            .sort((a, b) => domainInfo(a).title.localeCompare(domainInfo(b).title))
          if (!domains.length) return null
          return (
            <div className="directory__group" key={cat}>
              <h3 className="directory__cat">{cat}</h3>
              <ul className="index">
                {domains.map((d) => (
                  <ServiceRow key={d} domain={d} listings={byDomain[d]} open={open === d} onToggle={() => setOpen(open === d ? null : d)} />
                ))}
              </ul>
            </div>
          )
        })}
      </section>
    </div>
  )
}

const ServiceRow: React.FC<{ domain: string; listings: Listing[]; open: boolean; onToggle: () => void }> = ({
  domain,
  listings,
  open,
  onToggle,
}) => {
  const info = domainInfo(domain)
  const from = fromPrices(listings)
  return (
    <li className={open ? 'index__item is-open' : 'index__item'} data-testid={`service-${domain}`}>
      <button type="button" className="index__row" aria-expanded={open} onClick={onToggle}>
        <span className="index__title">{info.title}</span>
        <span className="index__leader" aria-hidden="true" />
        <span className="index__price num">
          from {from.map((f, i) => (
            <span key={f.asset}>
              {i > 0 && ', '}
              {money(f.price, f.asset)}
            </span>
          ))}
        </span>
        <span className="index__dots" aria-label={`${listings.length} vendors`}>
          {listings.map((l) => (
            <i key={l.id} style={{ background: vendorById(l.vendor.id)?.color }} />
          ))}
        </span>
      </button>
      <p className="index__summary">
        {info.summary} <span className="muted">{domain}</span>
      </p>
      {open && <Comparison listings={listings} />}
    </li>
  )
}

const Comparison: React.FC<{ listings: Listing[] }> = ({ listings }) => {
  const cheapest = Math.min(...listings.map(cheapestPrice))
  return (
    <div className="compare">
      <table className="compare__table" data-testid="comparison">
        <thead>
          <tr>
            <th scope="col">Vendor</th>
            <th scope="col">Pays in</th>
            <th scope="col" className="num-col">Per call</th>
            <th scope="col" className="num-col">30-day pass</th>
            <th scope="col">Status</th>
            <th scope="col"><span className="visually-hidden">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {listings.map((l, idx) => {
            const v = vendorById(l.vendor.id)
            const price = cheapestPrice(l)
            const second = listings.slice(0, idx).some((o) => o.vendor.id === l.vendor.id)
            return (
              <tr key={l.id} data-testid={`compare-${l.id}`}>
                <td>
                  <span className="compare__vendor">
                    <i style={{ background: v?.color }} aria-hidden="true" />
                    {l.vendor.name}
                    {second && <span className="muted compare__server">second server</span>}
                  </span>
                </td>
                <td data-testid="asset">{l.asset}</td>
                <td className="num-col num">
                  {money(price, l.asset)}
                  {price === cheapest && listings.length > 1 && <span className="compare__tag">lowest</span>}
                </td>
                <td className="num-col num">{l.pass ? money(l.pass.price, l.asset) : 'not sold'}</td>
                <td>{l.online ? 'Running' : <span className="muted">Stopped</span>}</td>
                <td className="compare__open">
                  <Link to={`/listing/${l.id}`} className="btn btn--small btn--quiet">
                    Open
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

const SettledFeed: React.FC = () => {
  const items = useSettlements(5)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <aside className="tape" aria-label="Recent payments">
      <h2 className="tape__title">Just settled</h2>
      {items.length === 0 ? (
        <p className="tape__empty">No payments in the latest blocks yet. The first call you pay for will appear here.</p>
      ) : (
        <ol className="tape__list">
          {items.map((t) => (
            <li key={t.txid}>
              <Link to={`/explorer/tx/${t.txid}`} className="tape__row">
                <span className="tape__amount num">{money(t.amount, resolveAssetName(t.asset))}</span>
                <span className="tape__to">to {t.vendorName}</span>
                <span className="tape__when muted">
                  block {t.round}, {ago(t.time, now)}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </aside>
  )
}
