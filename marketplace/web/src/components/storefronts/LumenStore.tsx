import React from 'react'
import { Link } from 'react-router-dom'
import type { StoreProps } from './types'
import { assetOf, earned } from './types'
import { domainInfo } from '../../lib/domains'
import { cheapestPrice, money } from '../../lib/catalog'
import { PassOffer } from '../PassOffer'

export const LumenStore: React.FC<StoreProps> = ({ identity, info, listings, passes, vendorPass, onBought }) => {
  const asset = assetOf(info, listings)
  return (
    <div className="store store--lumen">
      <div className="lumen">
        <header className="lumen__head">
          <div className="lumen__pool" aria-hidden="true" />
          <h1 className="lumen__name">{identity.name}</h1>
          <p className="lumen__tagline">{identity.tagline}</p>
          <p className="lumen__blurb">{identity.blurb}</p>
          <p className="lumen__facts">
            <span><span className="num">{listings.length}</span> services</span>
            <span>paid in {asset}</span>
            <span><span className="num">{money(earned(info), asset)}</span> earned</span>
          </p>
        </header>

        <section className="lumen__fixtures" aria-label="Services">
          {listings.map((l) => {
            const d = domainInfo(l.domain)
            const own = passes.find((p) => p.scope === `listing:${l.id}`)
            return (
              <Link key={l.id} to={`/listing/${l.id}`} className={l.online ? 'fixture is-lit' : 'fixture'}>
                <span className="fixture__lamp" aria-hidden="true" />
                <span className="fixture__name">{d.title}</span>
                <span className="fixture__price num">{money(cheapestPrice(l), l.asset)}</span>
                <span className="fixture__note">
                  {own ? 'pass held' : l.online ? 'running' : 'stopped'}
                </span>
              </Link>
            )
          })}
        </section>

        {info?.pass && (
          <PassOffer
            className="lumen__pass"
            scope={`vendor:${identity.id}`}
            title="Lumen pass"
            detail="All of Lumen's services, free for 30 days. Good only at Lumen Works."
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
