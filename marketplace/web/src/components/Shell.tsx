import React, { useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useWallet } from '@txnlab/use-wallet-react'
import { useBalances } from '../hooks/useBalances'
import { useBlocks } from '../hooks/useChain'
import { formatAmount, shortenAddress } from '../utils/format'

/** Four squares, one per vendor: the marketplace is the street they share. */
export const Mark: React.FC<{ size?: number }> = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
    <rect x="0" y="0" width="9" height="9" fill="var(--v-a)" />
    <rect x="11" y="0" width="9" height="9" fill="var(--v-b)" />
    <rect x="0" y="11" width="9" height="9" fill="var(--v-c)" />
    <rect x="11" y="11" width="9" height="9" fill="var(--v-d)" />
  </svg>
)

const NAV = [
  { to: '/', label: 'Services', end: true },
  { to: '/vendors', label: 'Vendors' },
  { to: '/explorer', label: 'Explorer' },
  { to: '/history', label: 'History' },
  { to: '/wallet', label: 'Wallet' },
]

export const Header: React.FC = () => {
  const { activeAddress } = useWallet()
  const { algo } = useBalances()
  return (
    <header className="topbar">
      <div className="topbar__inner">
        <Link to="/" className="wordmark">
          <Mark />
          <span>AI Service Marketplace</span>
        </Link>
        <nav className="topnav" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'topnav__link is-active' : 'topnav__link')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        {activeAddress ? (
          <Link to="/wallet" className="walletchip" title={activeAddress}>
            <span className="hash">{shortenAddress(activeAddress)}</span>
            <span className="walletchip__amount num" data-testid="balance-algo">
              {formatAmount(algo, 6)} ALGO
            </span>
          </Link>
        ) : (
          <Link to="/wallet" className="btn btn--small">
            Connect wallet
          </Link>
        )}
      </div>
      <ChainStrip />
    </header>
  )
}

function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(t)
  }, [ms])
  return now
}

export function ago(unixSeconds: number, now: number): string {
  const s = Math.max(0, Math.round(now / 1000 - unixSeconds))
  if (s < 60) return `${s} s ago`
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}

/** One quiet line under the navigation: the chain everyone here pays into, live. */
const ChainStrip: React.FC = () => {
  const { blocks, error } = useBlocks(1)
  const now = useNow()
  const head = blocks[0]
  return (
    <div className="chainstrip" role="status" aria-live="off">
      <div className="chainstrip__inner">
        {error ? (
          <span className="chainstrip__down">The chain is not reachable. Start LocalNet with algokit localnet start.</span>
        ) : head ? (
          <>
            <span className="chainstrip__pulse" aria-hidden="true" />
            <span>
              LocalNet block <Link to={`/explorer/block/${head.round}`} className="num">{head.round.toLocaleString('en-US')}</Link>
            </span>
            <span className="muted">sealed {ago(head.time, now)}</span>
            <span className="muted chainstrip__hash">
              hash <span className="hash">{head.hash.slice(0, 16)}</span>
            </span>
          </>
        ) : (
          <span className="muted">Reading the chain</span>
        )}
      </div>
    </div>
  )
}

export const Footer: React.FC = () => (
  <footer className="footer">
    <div className="footer__inner">
      <Mark size={14} />
      <p>
        Every payment on this site is a transaction on AlgoKit LocalNet. Open any of them in the <Link to="/explorer">explorer</Link>.
      </p>
    </div>
  </footer>
)
