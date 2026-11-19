import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useWallet } from '@txnlab/use-wallet-react'
import algosdk from 'algosdk'
import { faucet } from '../api'
import { useBalances } from '../hooks/useBalances'
import { usePasses } from '../hooks/usePasses'
import { formatAmount } from '../utils/format'
import { vendorById, vendorBySlug } from '../lib/vendors'
import { daysLeft, money, shortDate } from '../lib/catalog'
import { domainInfo } from '../lib/domains'

const PROVIDER_NOTES: Record<string, string> = {
  kmd: 'The developer wallet built into LocalNet. No setup.',
  lute: 'Browser wallet. Add LocalNet as a custom network first.',
  mnemonic: 'Paste a 25-word test phrase. For automated tests only.',
}

/** Groups an address into fours so a person can compare it by eye. */
function grouped(address: string): string {
  return address.match(/.{1,4}/g)?.join(' ') ?? address
}

export const WalletPage: React.FC = () => {
  const { wallets, activeWallet, activeAddress, algodClient, signTransactions } = useWallet()
  const { algo, musd, isOptedInMusd, musdAssetId } = useBalances()
  const { passes, loaded } = usePasses()
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  const act = async (key: string, fn: () => Promise<string>) => {
    setBusy(key)
    setNotice(null)
    try {
      setNotice({ kind: 'ok', text: await fn() })
    } catch (e: any) {
      setNotice({ kind: 'error', text: String(e.message || e).replace(/^API error \(\d+\): /, '') })
    } finally {
      setBusy(null)
    }
  }

  const fund = () =>
    act('faucet', async () => {
      const res = await faucet(activeAddress!)
      return res.message || 'Test funds sent. Balances update within a few seconds.'
    })

  const optIn = () =>
    act('optin', async () => {
      const sp = await algodClient.getTransactionParams().do()
      const txn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
        sender: activeAddress!,
        receiver: activeAddress!,
        amount: 0,
        assetIndex: musdAssetId,
        suggestedParams: sp,
      })
      const signed = await signTransactions([txn], [0])
      if (!signed?.[0]) throw new Error('The wallet did not sign the opt-in.')
      const { txid } = await algodClient.sendRawTransaction(signed[0]).do()
      await algosdk.waitForConfirmation(algodClient, txid, 4)
      return 'This wallet can now hold mUSD. Use the faucet again to receive 100 test mUSD.'
    })

  if (!activeAddress) {
    return (
      <div className="page passbook">
        <h1 className="passbook__title">Connect a wallet</h1>
        <p className="passbook__lede">
          Payments here are signed in your own wallet and go straight to the vendor. The marketplace never holds keys or
          money.
        </p>
        {notice && <p className={`notice notice--${notice.kind}`} data-testid="notice">{notice.text}</p>}
        <ul className="providers">
          {wallets.map((w) => {
            const key = w.id.toLowerCase()
            const note = Object.entries(PROVIDER_NOTES).find(([k]) => key.includes(k))?.[1]
            return (
              <li key={w.id}>
                <button
                  type="button"
                  className="provider"
                  data-testid={`connect-${key}`}
                  onClick={() => w.connect().catch((e: any) => setNotice({ kind: 'error', text: `Could not connect: ${e.message || e}` }))}
                >
                  <span className="provider__name">{w.metadata.name || w.id}</span>
                  {note && <span className="provider__note">{note}</span>}
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    )
  }

  return (
    <div className="page passbook">
      <header className="passbook__account">
        <div>
          <h1 className="passbook__title">Wallet</h1>
          <p className="passbook__addr hash" aria-label="Address">{grouped(activeAddress)}</p>
          <p className="muted">Connected with {activeWallet?.metadata.name ?? 'a wallet'}.</p>
        </div>
        <div className="passbook__actions">
          <button type="button" className="btn" data-testid="faucet-btn" disabled={busy !== null} onClick={fund}>
            {busy === 'faucet' ? 'Sending test funds' : 'Get test funds'}
          </button>
          <button type="button" className="btn btn--quiet" onClick={() => activeWallet?.disconnect()}>
            Disconnect
          </button>
        </div>
      </header>

      {notice && <p className={`notice notice--${notice.kind}`} data-testid="notice">{notice.text}</p>}

      <section className="passbook__section" aria-labelledby="holdings">
        <h2 id="holdings">Holdings</h2>
        <table className="holdings">
          <tbody>
            <tr>
              <th scope="row">
                ALGO
                <span>pays network fees, and every vendor except Blue Fern</span>
              </th>
              <td className="num" data-testid="balance-algo">{formatAmount(algo, 6)}</td>
              <td />
            </tr>
            <tr>
              <th scope="row">
                mUSD
                <span>the marketplace dollar token, asset {musdAssetId || 'unknown'}; Blue Fern is paid in it</span>
              </th>
              <td className="num" data-testid="balance-musd">{isOptedInMusd ? formatAmount(musd, 6) : 'not enabled'}</td>
              <td className="holdings__act">
                {!isOptedInMusd && (
                  <button type="button" className="btn btn--small btn--quiet" data-testid="optin-musd" disabled={busy !== null || !musdAssetId} onClick={optIn}>
                    {busy === 'optin' ? 'Waiting for the wallet' : 'Enable mUSD'}
                  </button>
                )}
              </td>
            </tr>
          </tbody>
        </table>
        <p className="passbook__fine">
          The faucet sends 10 ALGO, plus 100 mUSD once mUSD is enabled. It runs on LocalNet only, at most once a minute
          per wallet.
        </p>
      </section>

      <section className="passbook__section" aria-labelledby="passes">
        <h2 id="passes">Passes</h2>
        {!loaded && <p className="muted">Reading passes from the chain</p>}
        {loaded && passes.length === 0 && (
          <p className="passbook__fine">
            No passes yet. Each vendor sells a pass for a single service and one for all of its services; both last 30
            days and work only with that vendor. See the <Link to="/vendors">vendors</Link>.
          </p>
        )}
        <ul className="passes">
          {passes.map((p) => {
            const v = vendorById(p.vendor.id)
            const left = daysLeft(p.expiresAt)
            const what = p.kind === 'vendor' ? `Everything from ${p.vendor.name}` : `${domainInfo(p.listing?.domain ?? '').title} from ${p.vendor.name}`
            return (
              <li key={p.txid} className="pass" data-testid="my-pass" style={{ ['--edge' as string]: v?.color }}>
                <div className="pass__what">
                  <strong>{what}</strong>
                  <span className="muted">
                    Bought {shortDate(p.purchasedAt)} for {money(p.amount, p.asset)}, valid until {shortDate(p.expiresAt)}
                  </span>
                </div>
                <div className="pass__meter" aria-label={`${left} of 30 days left`}>
                  <span style={{ width: `${Math.min(100, (left / 30) * 100)}%` }} />
                </div>
                <span className="pass__left num">{left} days left</span>
                <span className="pass__links">
                  <Link to={p.listing ? `/listing/${p.listing.id}` : `/vendors/${vendorBySlug(p.vendor.id)?.slug ?? ''}`}>Open</Link>
                  <Link to={`/explorer/tx/${p.txid}`}>Receipt</Link>
                </span>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}
