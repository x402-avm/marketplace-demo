import { useCallback, useEffect, useState } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import { getPasses } from '../api'
import type { ActivePass } from '../types'

/** Active passes of the connected wallet, read back from the chain (indexer) every few seconds. */
export function usePasses() {
  const { activeAddress } = useWallet()
  const [passes, setPasses] = useState<ActivePass[]>([])
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(async () => {
    if (!activeAddress) {
      setPasses([])
      setLoaded(true)
      return []
    }
    try {
      const data = await getPasses(activeAddress)
      setPasses(data)
      return data
    } catch {
      return []
    } finally {
      setLoaded(true)
    }
  }, [activeAddress])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 6000)
    return () => clearInterval(t)
  }, [refresh])

  /** After a purchase the indexer needs a moment; poll until the new receipt shows up. */
  const waitFor = useCallback(
    async (txid: string) => {
      for (let i = 0; i < 30; i++) {
        const data = await refresh()
        if (data.some((p) => p.txid === txid)) return true
        await new Promise((r) => setTimeout(r, 1000))
      }
      return false
    },
    [refresh],
  )

  return { passes, loaded, refresh, waitFor }
}
