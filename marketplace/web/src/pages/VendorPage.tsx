import React from 'react'
import { Link, useParams } from 'react-router-dom'
import { useCatalog } from '../hooks/useCatalog'
import { usePasses } from '../hooks/usePasses'
import { vendorBySlug } from '../lib/vendors'
import type { StoreProps } from '../components/storefronts/types'
import { NovaStore } from '../components/storefronts/NovaStore'
import { FernStore } from '../components/storefronts/FernStore'
import { QuarryStore } from '../components/storefronts/QuarryStore'
import { LumenStore } from '../components/storefronts/LumenStore'

const STORES: Record<string, React.FC<StoreProps>> = {
  nova: NovaStore,
  fern: FernStore,
  quarry: QuarryStore,
  lumen: LumenStore,
}

export const VendorPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>()
  const identity = vendorBySlug(slug)
  const { listings, vendors, loading, error } = useCatalog()
  const { passes, waitFor } = usePasses()

  if (!identity) {
    return (
      <div className="page">
        <p className="notice notice--error">There is no vendor called “{slug}”.</p>
        <p style={{ marginTop: 16 }}>
          <Link to="/vendors">See all vendors</Link>
        </p>
      </div>
    )
  }
  if (loading) return <div className="page state">Opening {identity.name}</div>
  if (error) return <div className="page"><p className="notice notice--error">{error}</p></div>

  // A vendor may run two servers of the same service; buyers see one service, served by the first running server.
  const mine = listings
    .filter((l) => l.vendor.id === identity.id)
    .sort((a, b) => a.domain.localeCompare(b.domain) || Number(b.online) - Number(a.online) || (a.proxy_index ?? 0) - (b.proxy_index ?? 0))
  const own = mine.filter((l, i) => i === 0 || mine[i - 1].domain !== l.domain)
  const info = vendors.find((v) => v.id === identity.id)
  const vendorPass = passes.find((p) => p.scope === `vendor:${identity.id}`)
  const Store = STORES[identity.tone]
  return (
    <Store
      identity={identity}
      info={info}
      listings={own}
      passes={passes.filter((p) => p.vendor.id === identity.id)}
      vendorPass={vendorPass}
      onBought={waitFor}
    />
  )
}
