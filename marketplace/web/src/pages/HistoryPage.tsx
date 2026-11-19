import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useWallet } from '@txnlab/use-wallet-react'
import { getHistory } from '../api'
import type { HistoryItem } from '../types'
import { vendorByName } from '../lib/vendors'
import { domainInfo } from '../lib/domains'
import { money } from '../lib/catalog'
import { resolveAssetName } from '../utils/format'

function dayKey(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
}

function whatFor(h: HistoryItem): string {
  if (h.kind === 'pass') {
    if (h.scope?.startsWith('vendor:')) return `30-day pass for everything from ${h.vendor}`
    const listingId = h.scope?.replace('listing:', '') ?? ''
    const domain = listingId.replace(/-\d+$/, '')
    return `30-day pass for ${domainInfo(domain).title}`
  }
  if (h.listing) {
    const domain = h.listing.replace(/-\d+$/, '')
    return `${domainInfo(domain).title}${h.tool ? `, ${h.tool.replace(/_/g, ' ')}` : ''}`
  }
  return 'Service call'
}

export const HistoryPage: React.FC = () => {
  const { activeAddress } = useWallet()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    if (!activeAddress) {
      setItems([])
      setLoading(false)
      return
    }
    setLoading(true)
    getHistory(activeAddress)
      .then((d) => alive && setItems(d))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [activeAddress])

  const days = useMemo(() => {
    const out: [string, HistoryItem[]][] = []
    for (const h of items) {
      const k = h.time ? dayKey(h.time) : 'Not yet on chain'
      const last = out[out.length - 1]
      if (last && last[0] === k) last[1].push(h)
      else out.push([k, [h]])
    }
    return out
  }, [items])

  const totals = useMemo(() => {
    const t: Record<string, number> = {}
    for (const h of items) {
      const a = resolveAssetName(h.asset)
      t[a] = (t[a] ?? 0) + h.amount
    }
    return t
  }, [items])

  return (
    <div className="page statement">
      <header className="statement__head">
        <h1>Your payments</h1>
        {activeAddress && items.length > 0 && (
          <p className="statement__total">
            {items.length} payment{items.length > 1 ? 's' : ''},{' '}
            {Object.entries(totals).map(([a, v], i) => (
              <span key={a} className="num">
                {i > 0 && ' and '}
                {money(v, a)}
              </span>
            ))}{' '}
            in total.
          </p>
        )}
      </header>

      {!activeAddress && (
        <p className="statement__empty">
          <Link to="/wallet">Connect a wallet</Link> to see the calls and passes it has paid for.
        </p>
      )}
      {activeAddress && loading && <p className="state">Reading your payments from the chain</p>}
      {error && <p className="notice notice--error">{error}</p>}
      {activeAddress && !loading && !error && items.length === 0 && (
        <p className="statement__empty">
          No payments from this wallet yet. Pick a service in the <Link to="/">directory</Link> and pay for a call.
        </p>
      )}

      {days.map(([day, list]) => (
        <section key={day} className="statement__day" aria-label={day}>
          <h2 className="statement__date">{day}</h2>
          <ul className="stubs">
            {list.map((h) => {
              const v = vendorByName(h.vendor)
              return (
                <li key={h.txid} className="stub" data-testid="history-row" style={{ ['--edge' as string]: v?.color ?? 'var(--pencil-strong)' }}>
                  <span className="stub__amount num">{money(h.amount, resolveAssetName(h.asset))}</span>
                  <span className="stub__what">
                    <strong>{whatFor(h)}</strong>
                    <span className="muted">
                      {h.kind === 'pass' ? 'bought from' : 'paid to'} {h.vendor}
                    </span>
                  </span>
                  <span className="stub__when muted num">
                    {h.time ? new Date(h.time * 1000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                  <Link to={`/explorer/tx/${h.txid}`} className="stub__tx hash">
                    {h.txid.slice(0, 10)}
                  </Link>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
