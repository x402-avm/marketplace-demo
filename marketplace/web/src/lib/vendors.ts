/**
 * Storefront identities. Each vendor is a separate business with its own look; the marketplace shell only borrows
 * their colour for small markers (dots, receipt edges, the four-square mark).
 */
export type VendorTone = 'nova' | 'fern' | 'quarry' | 'lumen'

export interface VendorIdentity {
  id: string
  slug: string
  tone: VendorTone
  name: string
  /** marker colour used by the shell (dots, receipt edges) */
  color: string
  tagline: string
  blurb: string
}

export const VENDORS: Record<string, VendorIdentity> = {
  vendorA: {
    id: 'vendorA',
    slug: 'nova-labs',
    tone: 'nova',
    name: 'Nova Labs',
    color: '#1d55b4',
    tagline: 'The whole catalogue, charted.',
    blurb: 'Nova carries every kind of service in the marketplace at list price, settled in ALGO.',
  },
  vendorB: {
    id: 'vendorB',
    slug: 'blue-fern',
    tone: 'fern',
    name: 'Blue Fern AI',
    color: '#2f7d4f',
    tagline: 'Small prices, paid in mUSD.',
    blurb: 'Blue Fern charges a fifth under list and takes mUSD, the marketplace dollar token.',
  },
  vendorC: {
    id: 'vendorC',
    slug: 'quarry-compute',
    tone: 'quarry',
    name: 'Quarry Compute',
    color: '#d9a400',
    tagline: 'Prices posted per call.',
    blurb: 'Quarry runs the heavier half of the catalogue and posts one price for every call, settled in ALGO.',
  },
  vendorD: {
    id: 'vendorD',
    slug: 'lumen-works',
    tone: 'lumen',
    name: 'Lumen Works',
    color: '#e8892b',
    tagline: 'A short list, kept bright.',
    blurb: 'Lumen keeps a short list of services at one and a half times list, settled in ALGO.',
  },
}

export const VENDOR_ORDER = ['vendorA', 'vendorB', 'vendorC', 'vendorD']

export function vendorById(id?: string | null): VendorIdentity | undefined {
  return id ? VENDORS[id] : undefined
}

export function vendorBySlug(slug?: string | null): VendorIdentity | undefined {
  if (!slug) return undefined
  return Object.values(VENDORS).find((v) => v.slug === slug || v.id === slug)
}

export function vendorByName(name?: string | null): VendorIdentity | undefined {
  if (!name) return undefined
  return Object.values(VENDORS).find((v) => v.name === name)
}
