import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getTx } from '../api'
import { useVendorNames } from '../hooks/useCatalog'
import { formatAmount, resolveAssetName } from '../utils/format'

function decodeNote(b64?: string): string | null {
  if (!b64) return null
  try {
    const text = atob(b64)
    return /^[\x20-\x7e]+$/.test(text) ? text : null
  } catch {
    return null
  }
}

function describe(note: string | null): string | null {
  if (!note) return null
  if (note.startsWith('x402-pass:listing:')) return `30-day pass for service ${note.slice(18)}`
  if (note.startsWith('x402-pass:vendor:')) return '30-day pass for every service of this vendor'
  if (note.startsWith('x402-payment')) return 'Payment for one service call'
  if (note.startsWith('x402-fee-payer')) return 'Network fee, paid by the vendor'
  return null
}

export const TxPage: React.FC = () => {
  const { txid } = useParams<{ txid: string }>()
  const [tx, setTx] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const names = useVendorNames()

  useEffect(() => {
    if (!txid) return
    getTx(txid).then(setTx).catch((e) => setError(e.message))
  }, [txid])

  if (error) return <div className="page"><p className="notice notice--error">{error}</p></div>
  if (!tx) return <div className="page state">Reading transaction</div>

  const t = tx.transaction || tx
  const pay = t['payment-transaction']
  const axfer = t['asset-transfer-transaction']
  const amount = pay?.amount ?? axfer?.amount ?? 0
  const receiver = pay?.receiver ?? axfer?.receiver ?? ''
  const asset = axfer ? resolveAssetName(axfer['asset-id']) : 'ALGO'
  const round = t['confirmed-round']
  const when = t['round-time'] ? new Date(t['round-time'] * 1000).toLocaleString('en-GB') : ''
  const note = decodeNote(t.note)
  const purpose = describe(note)
  const who = (a: string) => (names[a] ? `${names[a]}` : null)

  return (
    <div className="page">
      <article className="receipt" aria-labelledby="receipt-title">
        <h1 id="receipt-title" className="receipt__title">Receipt</h1>
        <p className="receipt__amount num">
          {formatAmount(amount)} {asset}
        </p>
        {purpose && <p className="receipt__purpose">{purpose}</p>}
        <dl className="receipt__lines">
          <div>
            <dt>From</dt>
            <dd>{who(t.sender) && <strong>{who(t.sender)}</strong>}<span className="hash">{t.sender}</span></dd>
          </div>
          {receiver && (
            <div>
              <dt>To</dt>
              <dd>{who(receiver) && <strong>{who(receiver)}</strong>}<span className="hash">{receiver}</span></dd>
            </div>
          )}
          <div>
            <dt>Network fee</dt>
            <dd className="num">{formatAmount(t.fee ?? 0)} ALGO{t.fee === 0 ? ', covered by the other side of the group' : ''}</dd>
          </div>
          <div>
            <dt>Block</dt>
            <dd>
              <Link to={`/explorer/block/${round}`} className="num">{round}</Link>
              {when && <span className="muted">, {when}</span>}
            </dd>
          </div>
          {note && (
            <div>
              <dt>Note</dt>
              <dd className="hash">{note}</dd>
            </div>
          )}
          {t.group && (
            <div>
              <dt>Group</dt>
              <dd className="hash">{t.group}</dd>
            </div>
          )}
          <div>
            <dt>Transaction</dt>
            <dd className="hash">{t.id ?? txid}</dd>
          </div>
        </dl>
      </article>
    </div>
  )
}
