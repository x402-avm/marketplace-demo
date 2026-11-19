import type algosdk from 'algosdk'
import {
  payForRequirement as realPayForRequirement,
  buildIdentityTxn as realBuildIdentityTxn,
  encodeIdentityHeader as realEncodeIdentityHeader,
} from 'x402-avm-js'
import type { PaymentRequired } from 'x402-avm-js'

export async function payForRequirement(
  paymentRequired: PaymentRequired,
  payerAddress: string,
  algod: algosdk.Algodv2,
  signTxns: (txns: Uint8Array[], indexes: number[]) => Promise<(Uint8Array | null)[]>
): Promise<string> {
  const safeSignTxns = async (
    txns: Uint8Array[],
    indexes: number[]
  ): Promise<(Uint8Array | null)[]> => {
    const signed = await signTxns(txns, indexes)
    if (!signed) return new Array(txns.length).fill(null)
    const mapped: (Uint8Array | null)[] = new Array(txns.length).fill(null)
    if (signed.length === indexes.length) {
      indexes.forEach((idx, k) => {
        mapped[idx] = signed[k]
      })
    } else {
      signed.forEach((s, k) => {
        if (s) mapped[k] = s
      })
    }
    return mapped
  }
  // Demo cap: 10 ALGO / 10 mUSD per call. The wallet still asks the user to approve every payment.
  return realPayForRequirement(paymentRequired, payerAddress, algod, safeSignTxns, { maxAmount: 10_000_000n })
}

export function buildIdentityTxn(
  address: string,
  genesisHashB64: string,
  ts?: number
): algosdk.Transaction {
  return realBuildIdentityTxn(address, genesisHashB64, ts)
}

export function encodeIdentityHeader(signedBytes: Uint8Array): string {
  return realEncodeIdentityHeader(signedBytes)
}
