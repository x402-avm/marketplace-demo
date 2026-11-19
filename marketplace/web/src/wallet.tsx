import React, { useEffect, useState } from 'react'
import { WalletManager, WalletProvider } from '@txnlab/use-wallet-react'
import { kmd } from '@txnlab/use-wallet-kmd'
import { lute } from '@galaxypay/use-wallet-lute'
import { mnemonic } from '@txnlab/use-wallet-mnemonic'
import { getConfig } from './api'

export const DEFAULT_LOCALNET_GENESIS_HASH = 'qNF74lmmiHUCf7s3oewhYsMzOCOEptuJ9ytCk5gBPGI='

export function createWalletManager(genesisHash: string = DEFAULT_LOCALNET_GENESIS_HASH): WalletManager {
  const wallets = [
    kmd({
      baseServer: 'http://localhost',
      port: 4002,
      token: 'a'.repeat(64),
      wallet: 'unencrypted-default-wallet',
      promptForPassword: async () => '',
    }),
    lute({
      siteName: 'AI Service Marketplace',
    }),
  ]

  const enableMnemonic = Boolean(import.meta.env.DEV || import.meta.env.VITE_ENABLE_MNEMONIC === '1')
  if (enableMnemonic) {
    wallets.push(
      mnemonic({
        persistToStorage: true,
        promptForMnemonic: async () => {
          return window.prompt('Enter 25-word Algorand Mnemonic (dev/test only):')
        },
      })
    )
  }

  return new WalletManager({
    wallets,
    networks: {
      localnet: {
        algod: {
          baseServer: 'http://localhost',
          port: 4001,
          token: 'a'.repeat(64),
        },
        genesisHash,
        isTestnet: true,
      },
    },
    defaultNetwork: 'localnet',
  })
}

interface AppWalletProviderProps {
  children: React.ReactNode
}

export const AppWalletProvider: React.FC<AppWalletProviderProps> = ({ children }) => {
  const [manager, setManager] = useState<WalletManager | null>(null)

  useEffect(() => {
    let active = true

    async function init() {
      let genesisHash = DEFAULT_LOCALNET_GENESIS_HASH
      try {
        const cfg = await getConfig()
        if (active && cfg && cfg.genesisHash) {
          genesisHash = cfg.genesisHash
        }
      } catch (err) {
        console.warn('Could not load gateway config, using localnet defaults:', err)
      }

      if (active) {
        const mgr = createWalletManager(genesisHash)
        setManager(mgr)
      }
    }

    init()

    return () => {
      active = false
    }
  }, [])

  if (!manager) {
    return <div className="page state">Preparing wallet connections</div>
  }

  return (
    <WalletProvider manager={manager}>
      {children}
    </WalletProvider>
  )
}
