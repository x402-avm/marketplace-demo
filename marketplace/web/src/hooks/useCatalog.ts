import { useEffect, useState } from 'react'
import { getListings, getVendors } from '../api'
import type { Listing, VendorInfo } from '../types'

/** Listings and vendors (with on-chain earnings) for pages that need both. */
export function useCatalog() {
  const [listings, setListings] = useState<Listing[]>([])
  const [vendors, setVendors] = useState<VendorInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    Promise.all([getListings(), getVendors()])
      .then(([l, v]) => {
        if (!alive) return
        setListings(l)
        setVendors(v)
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  return { listings, vendors, loading, error }
}

let vendorNameCache: Record<string, string> | null = null

/** address -> vendor name, so the explorer can say "Nova Labs" instead of a 58-character address. */
export function useVendorNames(): Record<string, string> {
  const [names, setNames] = useState<Record<string, string>>(vendorNameCache ?? {})
  useEffect(() => {
    if (vendorNameCache) return
    getVendors()
      .then((vs) => {
        vendorNameCache = Object.fromEntries(vs.map((v) => [v.address, v.name]))
        setNames(vendorNameCache)
      })
      .catch(() => {})
  }, [])
  return names
}
