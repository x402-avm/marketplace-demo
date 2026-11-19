import algosdk from 'algosdk'
import { getPassQuote } from '../api'
import type { ActivePass, Listing, PassQuote } from '../types'

type SignFn = (txns: algosdk.Transaction[], indexes: number[]) => Promise<(Uint8Array | null)[]>

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

/**
 * Buy a pass the same way every payment here works: the gateway prepares one unsigned payment to the vendor, the
 * wallet signs it, and the browser sends it to the chain. Nobody but the buyer ever signs.
 */
export async function buyPass(
  scope: string,
  address: string,
  algod: algosdk.Algodv2,
  sign: SignFn,
): Promise<{ txid: string; quote: PassQuote }> {
  const quote = await getPassQuote(address, scope)
  const txn = algosdk.decodeUnsignedTransaction(base64ToBytes(quote.txn))
  const signed = await sign([txn], [0])
  if (!signed || !signed[0]) throw new Error('The wallet did not sign the pass payment.')
  const res = await algod.sendRawTransaction(signed[0]).do()
  await algosdk.waitForConfirmation(algod, res.txid, 6)
  return { txid: res.txid, quote }
}

export function serviceScope(listing: Listing): string {
  return `listing:${listing.id}`
}

export function vendorScope(vendorId: string): string {
  return `vendor:${vendorId}`
}

export function passFor(passes: ActivePass[], listing: Listing): ActivePass | undefined {
  return passes.find((p) => p.scope === serviceScope(listing) || p.scope === vendorScope(listing.vendor.id))
}
