import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { verifyChain } from '../api'
import type { ChainVerifyResponse } from '../types'
import { useBlocks } from '../hooks/useChain'
import { ago } from '../components/Shell'

export const ExplorerPage: React.FC = () => {
  const { blocks, error } = useBlocks(14)
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<ChainVerifyResponse | null>(null)
  const [checkError, setCheckError] = useState<string | null>(null)
  const head = blocks[0]
  const now = Date.now()

  const check = async () => {
    setChecking(true)
    setResult(null)
    setCheckError(null)
    try {
      setResult(await verifyChain(head ? Math.max(0, head.round - 200) : undefined, head?.round))
    } catch (e: any) {
      setCheckError(e.message)
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="page explorer">
      <header className="explorer__head">
        <div>
          <h1 className="explorer__round num">{head ? head.round.toLocaleString('en-US') : '...'}</h1>
          <p className="explorer__label">
            {head ? `blocks on LocalNet, the newest sealed ${ago(head.time, now)}` : 'Reading the chain'}
          </p>
        </div>
        <div className="explorer__verify">
          <p>
            Each block stores the hash of the one before it. Check that the last 200 blocks still link up, recomputing
            every hash here rather than trusting the node.
          </p>
          <button type="button" className="btn" onClick={check} disabled={checking || !head} data-testid="verify-chain">
            {checking ? 'Checking blocks' : 'Check the last 200 blocks'}
          </button>
          {result && (
            <p className={result.broken.length ? 'notice notice--error' : 'notice notice--ok'} data-testid="verify-result">
              {result.broken.length
                ? `${result.broken.length} of ${result.checked} links are broken.`
                : `${result.checked} blocks checked. Every block points at the one before it.`}
            </p>
          )}
          {checkError && <p className="notice notice--error">{checkError}</p>}
        </div>
      </header>

      {error && <p className="notice notice--error">{error}</p>}

      <section aria-labelledby="chain-title">
        <h2 id="chain-title" className="explorer__h2">Latest blocks, newest first</h2>
        <ol className="chain">
          {blocks.map((b, i) => {
            const older = blocks[i + 1]
            const linked = older ? b.prevHash === older.hash : null
            return (
              <li key={b.round} className="chain__item">
                <Link to={`/explorer/block/${b.round}`} className={b.txCount ? 'chain__block has-tx' : 'chain__block'} data-testid="block-row">
                  <span className="chain__round num">{b.round}</span>
                  <span className="chain__tx">{b.txCount ? `${b.txCount} transaction${b.txCount > 1 ? 's' : ''}` : 'empty'}</span>
                  <span className="chain__hash hash">{b.hash.slice(0, 12)}</span>
                  <span className="chain__time muted">{ago(b.time, now)}</span>
                </Link>
                {older && (
                  <span
                    className={linked ? 'chain__link is-ok' : 'chain__link is-broken'}
                    role="img"
                    aria-label={`${linked ? 'linked to' : 'not linked to'} block ${older.round}`}
                    title={linked ? 'This block names the next one as its parent' : 'Hash link broken'}
                  />
                )}
              </li>
            )
          })}
        </ol>
      </section>
    </div>
  )
}
