import React from 'react'
import { Link } from 'react-router-dom'
import type { StoreProps } from './types'
import { assetOf, earned } from './types'
import { CATEGORIES, domainInfo } from '../../lib/domains'
import { money, toolPrices } from '../../lib/catalog'
import { PassOffer } from '../PassOffer'

/** Rock grades for the five categories, used as the band on the left of each board section. */
const GRADE: Record<string, string> = {
  'Speech and sound': '#c7923e',
  'Images and video': '#a2462c',
  Documents: '#6b7480',
  'Research and the web': '#b9a37c',
  Code: '#3b4148',
}

export const QuarryStore: React.FC<StoreProps> = ({ identity, info, listings, passes, vendorPass, onBought }) => {
  const asset = assetOf(info, listings)
  const ordered = [...listings].sort(
    (a, b) =>
      CATEGORIES.indexOf(domainInfo(a.domain).category as (typeof CATEGORIES)[number]) -
        CATEGORIES.indexOf(domainInfo(b.domain).category as (typeof CATEGORIES)[number]) || a.domain.localeCompare(b.domain),
  )
  return (
    <div className="store store--quarry">
      <div className="quarry">
        <header className="quarry__head">
          <h1 className="quarry__name">{identity.name}</h1>
          <div className="quarry__meta">
            <p className="quarry__tagline">{identity.tagline}</p>
            <p className="quarry__blurb">{identity.blurb}</p>
            <dl className="quarry__facts">
              <div><dt>Services</dt><dd className="num">{listings.length}</dd></div>
              <div><dt>Paid in</dt><dd>{asset}</dd></div>
              <div><dt>Earned so far</dt><dd className="num">{money(earned(info), asset)}</dd></div>
            </dl>
          </div>
        </header>

        <section className="board" aria-labelledby="board-title">
          <div className="board__head">
            <h2 id="board-title">Posted prices</h2>
            <p>{asset} per call. Prices change only when this board does.</p>
          </div>
          {ordered.map((l) => {
            const d = domainInfo(l.domain)
            const prices = toolPrices(l)
            const own = passes.find((p) => p.scope === `listing:${l.id}`)
            return (
              <div className="board__lot" key={l.id} style={{ ['--grade' as string]: GRADE[d.category] ?? '#6b7480' }}>
                <div className="board__lotname">
                  <Link to={`/listing/${l.id}`}>{d.title}</Link>
                  <span>{l.online ? 'running' : 'stopped'}</span>
                </div>
                <table className="board__table">
                  <tbody>
                    {Object.entries(prices).map(([tool, price]) => (
                      <tr key={tool}>
                        <th scope="row">{tool.replace(/_/g, ' ')}</th>
                        <td className="num">{money(price, l.asset)}</td>
                      </tr>
                    ))}
                    {l.pass && (
                      <tr className="board__passrow">
                        <th scope="row">{own ? '30-day pass, held' : '30-day pass for this service'}</th>
                        <td className="num">{money(l.pass.price, l.asset)}</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )
          })}
        </section>

        {info?.pass && (
          <PassOffer
            className="quarry__pass"
            scope={`vendor:${identity.id}`}
            title="Quarry pass"
            detail="Every service on this board, free for 30 days. Good only at Quarry Compute."
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
