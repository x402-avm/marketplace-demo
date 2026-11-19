import React, { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { StoreProps } from './types'
import { assetOf, earned } from './types'
import { CATEGORIES, domainInfo } from '../../lib/domains'
import { cheapestPrice, money } from '../../lib/catalog'
import { PassOffer } from '../PassOffer'
import type { Listing } from '../../types'

const W = 880
const H = 560
const CX = W / 2
const CY = H / 2

/** Each category owns a slice of the sky; its services are stars joined into one figure. */
function layout(listings: Listing[]) {
  const groups = CATEGORIES.map((c) => listings.filter((l) => domainInfo(l.domain).category === c)).filter((g) => g.length)
  // every category gets a readable slice of sky, however few services it holds
  const weights = groups.map((g) => g.length + 2)
  const total = weights.reduce((x, y) => x + y, 0)
  const RINGS = [150, 245, 195, 290, 125, 225]
  let start = -Math.PI / 2
  const stars: { l: Listing; x: number; y: number; r: number; cat: string; left: boolean }[] = []
  const labels: { cat: string; x: number; y: number; anchor: 'start' | 'end' | 'middle' }[] = []
  const prices = listings.map(cheapestPrice)
  const lo = Math.min(...prices)
  const hi = Math.max(...prices)
  groups.forEach((g, gi) => {
    const span = (weights[gi] / total) * Math.PI * 2
    g.forEach((l, i) => {
      const t = g.length === 1 ? 0.5 : i / (g.length - 1)
      const a = start + span * (0.18 + 0.64 * t)
      const rad = RINGS[i % RINGS.length]
      const p = cheapestPrice(l)
      const size = hi === lo ? 5 : 3.5 + ((p - lo) / (hi - lo)) * 5
      const x = CX + Math.cos(a) * rad * 1.35
      stars.push({ l, x, y: CY + Math.sin(a) * rad * 0.8, r: size, cat: domainInfo(l.domain).category, left: x < CX })
    })
    const mid = start + span / 2
    labels.push({
      cat: domainInfo(g[0].domain).category,
      x: CX + Math.cos(mid) * 420,
      y: CY + Math.sin(mid) * 262,
      anchor: Math.cos(mid) > 0.3 ? 'end' : Math.cos(mid) < -0.3 ? 'start' : 'middle',
    })
    start += span
  })
  return { stars, labels }
}

export const NovaStore: React.FC<StoreProps> = ({ identity, info, listings, passes, vendorPass, onBought }) => {
  const navigate = useNavigate()
  const { stars, labels } = useMemo(() => layout(listings), [listings])
  const [hover, setHover] = useState<string | null>(null)
  const asset = assetOf(info, listings)
  const hovered = stars.find((s) => s.l.id === hover)

  return (
    <div className="store store--nova">
      <div className="nova">
        <header className="nova__head">
          <h1 className="nova__name">{identity.name}</h1>
          <p className="nova__tagline">{identity.tagline}</p>
          <p className="nova__blurb">{identity.blurb}</p>
          <dl className="nova__facts">
            <div><dt>Services</dt><dd className="num">{listings.length}</dd></div>
            <div><dt>Paid in</dt><dd>{asset}</dd></div>
            <div><dt>Earned so far</dt><dd className="num">{money(earned(info), asset)}</dd></div>
          </dl>
        </header>

        <figure className="nova__chart">
          <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Chart of ${listings.length} services`}>
            {[120, 210, 300].map((r) => (
              <ellipse key={r} cx={CX} cy={CY} rx={r * 1.35} ry={r * 0.82} className="grat" />
            ))}
            {Array.from({ length: 12 }, (_, i) => {
              const a = (i / 12) * Math.PI * 2
              return <line key={i} x1={CX} y1={CY} x2={CX + Math.cos(a) * 430} y2={CY + Math.sin(a) * 270} className="grat grat--ray" />
            })}
            {CATEGORIES.map((c) => {
              const pts = stars.filter((s) => s.cat === c)
              return pts.length > 1 ? <polyline key={c} points={pts.map((s) => `${s.x},${s.y}`).join(' ')} className="join" /> : null
            })}
            {labels.map((lb) => (
              <text key={lb.cat} x={lb.x} y={lb.y} textAnchor={lb.anchor} className="catlabel">
                {lb.cat}
              </text>
            ))}
            {stars.map((s) => (
              <g
                key={s.l.id}
                className={hover === s.l.id ? 'starnode is-hot' : 'starnode'}
                role="link"
                tabIndex={0}
                aria-label={`${domainInfo(s.l.domain).title}, from ${money(cheapestPrice(s.l), s.l.asset)}`}
                onMouseEnter={() => setHover(s.l.id)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(s.l.id)}
                onBlur={() => setHover(null)}
                onClick={() => navigate(`/listing/${s.l.id}`)}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && navigate(`/listing/${s.l.id}`)}
              >
                <circle cx={s.x} cy={s.y} r={s.r + 9} className="hit" />
                <circle cx={s.x} cy={s.y} r={s.r} className="core" />
                <text x={s.left ? s.x - s.r - 7 : s.x + s.r + 7} y={s.y + 4} textAnchor={s.left ? 'end' : 'start'} className="starlabel">
                  {domainInfo(s.l.domain).title}
                </text>
              </g>
            ))}
          </svg>
          <figcaption className="nova__caption">
            {hovered ? (
              <>
                <strong>{domainInfo(hovered.l.domain).title}</strong> from {money(cheapestPrice(hovered.l), hovered.l.asset)} a call.{' '}
                {domainInfo(hovered.l.domain).summary}
              </>
            ) : (
              'Each star is a service. Brighter stars cost more per call. Select one to open it.'
            )}
          </figcaption>
        </figure>

        <section className="nova__catalogue" aria-labelledby="nova-cat">
          <h2 id="nova-cat">Catalogue</h2>
          <ul>
            {listings.map((l) => {
              const d = domainInfo(l.domain)
              const own = passes.find((p) => p.scope === `listing:${l.id}`)
              return (
                <li key={l.id}>
                  <Link to={`/listing/${l.id}`}>
                    <span className="nova__svc">{d.title}</span>
                    <span className="nova__price num">{money(cheapestPrice(l), l.asset)}</span>
                  </Link>
                  <p>{d.summary}{own ? ' You hold a pass for this service.' : ''}</p>
                </li>
              )
            })}
          </ul>
        </section>

        {info?.pass && (
          <PassOffer
            className="nova__pass"
            scope={`vendor:${identity.id}`}
            title={`The Nova pass`}
            detail={`Every Nova service, free for ${30} days. Good only at Nova Labs.`}
            price={info.pass.price}
            asset={asset}
            active={vendorPass}
            onBought={onBought}
            testid="vendor-pass"
          />
        )}
      </div>
    </div>
  )
}
