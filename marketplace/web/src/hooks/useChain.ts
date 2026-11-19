import { useEffect, useState } from 'react'
import { getBlock, getBlocks, getVendors } from '../api'
import type { BlockHeaderItem, BlockTxnItem, VendorInfo } from '../types'

/** Latest blocks, refreshed every 3 seconds. */
export function useBlocks(limit = 12) {
  const [blocks, setBlocks] = useState<BlockHeaderItem[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const data = await getBlocks(limit)
        if (alive) {
          setBlocks(data)
          setError(null)
        }
      } catch (e: any) {
        if (alive) setError(e.message || 'Cannot reach the chain')
      }
    }
    load()
    const t = setInterval(load, 3000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [limit])
  return { blocks, error }
}

export interface Settlement extends BlockTxnItem {
  round: number
  time: number
  vendorName?: string
}

/** The most recent marketplace payments (calls and passes) found in the latest blocks. */
export function useSettlements(count = 5) {
  const [items, setItems] = useState<Settlement[]>([])
  useEffect(() => {
    let alive = true
    let vendors: VendorInfo[] = []
    const load = async () => {
      try {
        if (!vendors.length) vendors = await getVendors().catch(() => [])
        const byAddr = Object.fromEntries(vendors.map((v) => [v.address, v.name]))
        const heads = await getBlocks(40)
        const withTx = heads.filter((b) => b.txCount > 0).slice(0, 12)
        const details = await Promise.all(withTx.map((b) => getBlock(b.round).catch(() => null)))
        const out: Settlement[] = []
        for (const d of details) {
          if (!d) continue
          const head = withTx.find((b) => b.round === d.round)
          for (const t of d.txns) {
            if (!byAddr[t.to] || !t.amount) continue
            out.push({ ...t, round: d.round, time: head?.time ?? 0, vendorName: byAddr[t.to] })
          }
        }
        if (alive) setItems(out.slice(0, count))
      } catch {
        /* the feed is decoration on top of real data; stay quiet when the chain is unreachable */
      }
    }
    load()
    const t = setInterval(load, 8000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [count])
  return items
}
