import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useWallet } from '@txnlab/use-wallet-react'
import type { ActivePass } from '../types'
import { buyPass } from '../lib/passes'
import { daysLeft, money, shortDate } from '../lib/catalog'

interface Props {
  scope: string
  title: string
  detail: string
  price: number
  asset: string
  active?: ActivePass
  onBought: (txid: string) => Promise<unknown>
  testid: string
  className?: string
}

/** One pass for sale. Bought with a single wallet-signed payment straight to the vendor. */
export const PassOffer: React.FC<Props> = ({ scope, title, detail, price, asset, active, onBought, testid, className }) => {
  const { activeAddress, algodClient, signTransactions } = useWallet()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const buy = async () => {
    if (!activeAddress || !algodClient) return
    setBusy(true)
    setError(null)
    try {
      const { txid } = await buyPass(scope, activeAddress, algodClient, (txns, idx) => signTransactions(txns, idx))
      await onBought(txid)
    } catch (e: any) {
      setError(String(e.message || e).replace(/^API error \(\d+\): /, ''))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`passoffer ${active ? 'is-active' : ''} ${className ?? ''}`} data-testid={testid}>
      <div className="passoffer__text">
        <p className="passoffer__title">{title}</p>
        <p className="passoffer__detail">{detail}</p>
      </div>
      {active ? (
        <p className="passoffer__state" data-testid={`${testid}-status`}>
          Active until {shortDate(active.expiresAt)}, {daysLeft(active.expiresAt)} days left.{' '}
          <Link to={`/explorer/tx/${active.txid}`}>Receipt</Link>
        </p>
      ) : (
        <div className="passoffer__buy">
          <span className="passoffer__price num">{money(price, asset)}</span>
          <button type="button" className="passoffer__btn" disabled={busy || !activeAddress} onClick={buy} data-testid={`${testid}-buy`}>
            {busy ? 'Waiting for the wallet' : 'Buy pass'}
          </button>
        </div>
      )}
      {!activeAddress && !active && <p className="passoffer__hint">Connect a wallet to buy a pass.</p>}
      {error && <p className="passoffer__error" role="alert">{error}</p>}
    </div>
  )
}
