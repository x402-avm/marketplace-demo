import { useState, useEffect } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import { getConfig } from '../api'

export interface AccountBalances {
  algo: number // in microAlgos
  musd: number // in base units
  aiSub: number // amount of asset
  isOptedInMusd: boolean
  isOptedInAiSub: boolean
  musdAssetId: number
  aiSubAssetId: number
  loading: boolean
}

export function useBalances() {
  const { activeAddress, algodClient } = useWallet()
  const [balances, setBalances] = useState<AccountBalances>({
    algo: 0,
    musd: 0,
    aiSub: 0,
    isOptedInMusd: false,
    isOptedInAiSub: false,
    musdAssetId: 0,
    aiSubAssetId: 0,
    loading: true,
  })

  useEffect(() => {
    let active = true

    async function fetchBalances() {
      if (!activeAddress || !algodClient) {
        if (active) {
          setBalances((prev) => ({ ...prev, algo: 0, musd: 0, aiSub: 0, loading: false }))
        }
        return
      }

      try {
        let musdId = 0
        let aiSubId = 0
        try {
          const cfg = await getConfig()
          if (cfg && cfg.assets) {
            musdId = cfg.assets['mUSD'] || 0
            aiSubId = cfg.assets['AI-SUB'] || 0
          }
        } catch {
          // ignore if config offline
        }

        const info = await algodClient.accountInformation(activeAddress).do()
        const algoAmount = Number(info.amount || 0)

        let musdAmount = 0
        let isOptedMusd = false
        let aiSubAmount = 0
        let isOptedAiSub = false

        if (Array.isArray(info.assets)) {
          for (const a of info.assets) {
            const assetId = Number(a.assetId || (a as any)['asset-id'])
            const amt = Number(a.amount || 0)
            if (musdId && assetId === musdId) {
              musdAmount = amt
              isOptedMusd = true
            }
            if (aiSubId && assetId === aiSubId) {
              aiSubAmount = amt
              isOptedAiSub = true
            }
          }
        }

        if (active) {
          setBalances({
            algo: algoAmount,
            musd: musdAmount,
            aiSub: aiSubAmount,
            isOptedInMusd: isOptedMusd,
            isOptedInAiSub: isOptedAiSub,
            musdAssetId: musdId,
            aiSubAssetId: aiSubId,
            loading: false,
          })
        }
      } catch (err) {
        console.warn('Failed to fetch account balances:', err)
        if (active) {
          setBalances((prev) => ({ ...prev, loading: false }))
        }
      }
    }

    fetchBalances()
    const interval = setInterval(fetchBalances, 4000)

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [activeAddress, algodClient])

  return balances
}
