import React from 'react'
import { Link } from 'react-router-dom'
import type { StoreProps } from './types'
import { assetOf, earned } from './types'
import { domainInfo } from '../../lib/domains'
import { cheapestPrice, money, toolPrices } from '../../lib/catalog'
import { PassOffer } from '../PassOffer'
import { Frond } from './motifs'

export const FernStore: React.FC<StoreProps> = ({ identity, info, listings, passes, vendorPass, onBought }) => {
  const asset = assetOf(info, listings)
  return (
    <div className="store store--fern">
      <div className="fern">
        <header className="fern__head">
          <div className="fern__title">
            <h1 className="fern__name">{identity.name}</h1>
            <p className="fern__tagline">{identity.tagline}</p>
            <p className="fern__blurb">{identity.blurb}</p>
          </div>
          <div className="fern__frond" aria-hidden="true">
            <Frond leaves={18} />
          </div>
        </header>

        <div className="fern__strip">
          <p>
            <span className="num">{listings.length}</span> services
          </p>
          <p>paid in {asset}</p>
          <p>
            <span className="num">{money(earned(info), asset)}</span> earned so far
          </p>
        </div>

        <section className="fern__plates" aria-label="Services">
          {listings.map((l) => {
            const d = domainInfo(l.domain)
            const tools = Object.keys(toolPrices(l))
            const own = passes.find((p) => p.scope === `listing:${l.id}`)
            return (
              <Link key={l.id} to={`/listing/${l.id}`} className="plate">
                <span className="plate__family">{d.category}</span>
                <h2 className="plate__name">{d.title}</h2>
                <p className="plate__desc">{d.summary}</p>
                <p className="plate__tools">{tools.map((t) => t.replace(/_/g, ' ')).join(', ')}</p>
                <div className="plate__foot">
                  <span>
                    <span className="num plate__price">{money(cheapestPrice(l), l.asset)}</span> a call
                  </span>
                  <span className="plate__pass">
                    {own ? 'pass held' : l.pass ? `${money(l.pass.price, l.asset)} for 30 days` : ''}
                  </span>
                </div>
              </Link>
            )
          })}
        </section>

        {info?.pass && (
          <PassOffer
            className="fern__pass"
            scope={`vendor:${identity.id}`}
            title="A season with Blue Fern"
            detail="Every Blue Fern service, free for 30 days. Paid in mUSD, good only at Blue Fern."
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
