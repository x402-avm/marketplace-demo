import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getBlock } from '../api'
import type { BlockDetail } from '../types'
import { useVendorNames } from '../hooks/useCatalog'
import { formatAmount, resolveAssetName, shortenAddress } from '../utils/format'

export const BlockPage: React.FC = () => {
  const { round } = useParams<{ round: string }>()
  const n = Number(round)
  const [block, setBlock] = useState<BlockDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const names = useVendorNames()

  useEffect(() => {
    setBlock(null)
    setError(null)
    if (!Number.isInteger(n) || n < 0) {
      setError('A block number is a whole number, 0 or more.')
      return
    }
    getBlock(n).then(setBlock).catch((e) => setError(e.message))
  }, [n])

  return (
    <div className="page ledger">
      <nav className="ledger__nav">
        <Link to="/explorer">All blocks</Link>
        <span className="ledger__step">
          {n > 0 && <Link to={`/explorer/block/${n - 1}`}>Block {n - 1}</Link>}
          <Link to={`/explorer/block/${n + 1}`}>Block {n + 1}</Link>
        </span>
      </nav>
      <h1 className="ledger__title">Block #{round}</h1>
      {error && <p className="notice notice--error">{error}</p>}
      {!block && !error && <p className="state">Reading block {round}</p>}
      {block && (
        <>
          <dl className="ledger__sheet">
            <div>
              <dt>Hash</dt>
              <dd className="hash">{block.hash}</dd>
            </div>
            <div>
              <dt>Parent</dt>
              <dd className="hash">
                {block.round > 0 ? <Link to={`/explorer/block/${block.round - 1}`}>{block.prevHash}</Link> : block.prevHash}
              </dd>
            </div>
            <div>
              <dt>Check</dt>
              <dd>
                {block.hashOk ? (
                  <span className="seal seal--ok" data-testid="hash-ok">
                    Hash recomputed here and it matches
                  </span>
                ) : (
                  <span className="seal seal--bad" data-testid="hash-bad">
                    Recomputed hash does not match
                  </span>
                )}
              </dd>
            </div>
          </dl>

          <h2 className="ledger__h2">
            {block.txns.length ? `${block.txns.length} transaction${block.txns.length > 1 ? 's' : ''}` : 'No transactions in this block'}
          </h2>
          {block.txns.length > 0 && (
            <div className="ledger__scroll">
              <table className="ledger__table">
                <thead>
                  <tr>
                    <th scope="col">Transaction</th>
                    <th scope="col">Kind</th>
                    <th scope="col">From</th>
                    <th scope="col">To</th>
                    <th scope="col" className="r">Amount</th>
                    <th scope="col" className="r">Fee</th>
                  </tr>
                </thead>
                <tbody>
                  {block.txns.map((t) => (
                    <tr key={t.txid}>
                      <td>
                        <Link to={`/explorer/tx/${t.txid}`} className="hash">{t.txid.slice(0, 12)}</Link>
                      </td>
                      <td>{t.type === 'pay' ? 'payment' : t.type === 'axfer' ? 'asset transfer' : t.type}</td>
                      <td>{names[t.from] ?? <span className="hash">{shortenAddress(t.from, 5)}</span>}</td>
                      <td>{names[t.to] ?? <span className="hash">{shortenAddress(t.to, 5)}</span>}</td>
                      <td className="r num">
                        {formatAmount(t.amount)} {resolveAssetName(t.asset)}
                      </td>
                      <td className="r num">{formatAmount(t.fee)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
