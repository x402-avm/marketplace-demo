import React from 'react'
import { Link } from 'react-router-dom'
import { useCatalog } from '../hooks/useCatalog'
import { VENDORS, VENDOR_ORDER } from '../lib/vendors'
import { money } from '../lib/catalog'
import { Constellation, Frond, Strata, Glow } from '../components/storefronts/motifs'
import type { VendorInfo } from '../types'

const MOTIF = { nova: Constellation, fern: Frond, quarry: Strata, lumen: Glow }

export const VendorsPage: React.FC = () => {
  const { vendors, listings, error, loading } = useCatalog()
  return (
    <div className="page vendors">
      <header className="vendors__head">
        <h1>Four vendors, one street.</h1>
        <p className="vendors__sub">
          Each vendor runs its own servers, sets its own prices and is paid directly. A pass bought from one vendor is
          good only with that vendor.
        </p>
      </header>
      {error && <p className="notice notice--error">{error}</p>}
      {loading && <p className="state">Loading vendors</p>}
      <div className="posters">
        {VENDOR_ORDER.map((id) => {
          const ident = VENDORS[id]
          const info: VendorInfo | undefined = vendors.find((v) => v.id === id)
          const count = listings.filter((l) => l.vendor.id === id).length
          const Motif = MOTIF[ident.tone]
          const earned = info ? info.earnings[info.asset] ?? 0 : 0
          return (
            <Link key={id} to={`/vendors/${ident.slug}`} className={`poster poster--${ident.tone}`} data-testid={`poster-${id}`}>
              <div className="poster__motif" aria-hidden="true">
                <Motif seed={id} />
              </div>
              <div className="poster__body">
                <h2 className="poster__name">{ident.name}</h2>
                <p className="poster__tagline">{ident.tagline}</p>
                <dl className="poster__facts">
                  <div>
                    <dt>Services</dt>
                    <dd className="num">{count || info?.listings || 0}</dd>
                  </div>
                  <div>
                    <dt>Paid in</dt>
                    <dd>{info?.asset ?? (id === 'vendorB' ? 'mUSD' : 'ALGO')}</dd>
                  </div>
                  <div>
                    <dt>Earned so far</dt>
                    <dd className="num">{info ? money(earned, info.asset) : 'reading'}</dd>
                  </div>
                </dl>
                <span className="poster__visit">Visit {ident.name}</span>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
