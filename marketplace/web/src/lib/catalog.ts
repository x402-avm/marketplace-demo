import type { Listing } from '../types'
import { formatAmount } from '../utils/format'

export function toolPrices(listing: Listing): Record<string, number> {
  if (listing.prices && Object.keys(listing.prices).length > 0) return listing.prices
  return Object.fromEntries((listing.tools ?? []).map((t) => [t.name, t.price]))
}

export function cheapestPrice(listing: Listing): number {
  const values = Object.values(toolPrices(listing))
  return values.length ? Math.min(...values) : 0
}

/** Cheapest call per asset across a set of listings, ALGO first. */
export function fromPrices(listings: Listing[]): { asset: string; price: number }[] {
  const best: Record<string, number> = {}
  for (const l of listings) {
    const p = cheapestPrice(l)
    if (!p) continue
    if (best[l.asset] === undefined || p < best[l.asset]) best[l.asset] = p
  }
  return Object.entries(best)
    .map(([asset, price]) => ({ asset, price }))
    .sort((a, b) => (a.asset === 'ALGO' ? -1 : b.asset === 'ALGO' ? 1 : a.asset.localeCompare(b.asset)))
}

export function groupByDomain(listings: Listing[]): Record<string, Listing[]> {
  const out: Record<string, Listing[]> = {}
  for (const l of listings) {
    ;(out[l.domain] ??= []).push(l)
  }
  for (const k of Object.keys(out)) out[k].sort((a, b) => (a.proxy_index ?? 0) - (b.proxy_index ?? 0))
  return out
}

/** "0.02 ALGO" — amounts are stored in base units with 6 decimals for both ALGO and mUSD. */
export function money(baseUnits: number, asset: string): string {
  return `${formatAmount(baseUnits, 6)} ${asset}`
}

export function daysLeft(expiresAt: number, now: number = Date.now() / 1000): number {
  return Math.max(0, Math.ceil((expiresAt - now) / 86400))
}

export function shortDate(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
