import type { ActivePass, Listing, VendorInfo } from '../../types'
import type { VendorIdentity } from '../../lib/vendors'

export interface StoreProps {
  identity: VendorIdentity
  info?: VendorInfo
  listings: Listing[]
  passes: ActivePass[]
  vendorPass?: ActivePass
  onBought: (txid: string) => Promise<unknown>
}

export function earned(info?: VendorInfo): number {
  return info ? info.earnings[info.asset] ?? 0 : 0
}

export function assetOf(info: VendorInfo | undefined, listings: { asset: string }[]): string {
  return info?.asset ?? listings[0]?.asset ?? 'ALGO'
}
