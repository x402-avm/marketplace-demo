import React, { useRef, useState } from 'react'
import { PayButton, RawOutput, getFileUrl } from '../kit'
import type { ToolUIProps } from '../kit'
import './invoice.css'

export const domain = 'invoice_mcp'

const TOOL = 'generate_invoice'

interface Row {
  key: number
  name: string
  quantity: string
  amount: string
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const round2 = (n: number) => Math.round(n * 100) / 100

function rowState(r: Row) {
  const name = r.name.trim()
  const qty = Number(r.quantity)
  const price = Number(r.amount)
  const qtyOk = r.quantity.trim() !== '' && Number.isInteger(qty) && qty > 0
  const priceOk = r.amount.trim() !== '' && Number.isFinite(price) && price >= 0
  const blank = !name && !r.quantity.trim() && !r.amount.trim()
  return { name, qty, price, qtyOk, priceOk, blank, ok: Boolean(name) && qtyOk && priceOk, line: qtyOk && priceOk ? qty * price : 0 }
}

function invoiceLabel(payLabel: string): string {
  if (/^Run with your pass/.test(payLabel)) return 'Make the invoice PDF with your pass'
  return payLabel.replace(/ and run$/, ' and make the invoice PDF')
}

const InvoiceBuilder: React.FC<ToolUIProps> = (props) => {
  const { run, running, result, text, canRun, listing } = props
  const nextKey = useRef(3)
  const [customer, setCustomer] = useState('Harbour Street Bakery')
  const [rows, setRows] = useState<Row[]>([
    { key: 1, name: 'Website redesign', quantity: '1', amount: '1200' },
    { key: 2, name: 'Product photography, per hour', quantity: '6', amount: '85' },
  ])
  const [taxRate, setTaxRate] = useState('8')
  const [touched, setTouched] = useState(false)
  const nameRefs = useRef<Record<number, HTMLInputElement | null>>({})

  const states = rows.map(rowState)
  const filled = rows.map((r, i) => ({ r, s: states[i] })).filter((x) => !x.s.blank)
  const subtotal = round2(filled.reduce((a, x) => a + x.s.line, 0))
  const rate = Number(taxRate)
  const rateOk = taxRate.trim() === '' || (Number.isFinite(rate) && rate >= 0 && rate <= 100)
  const tax = rateOk && taxRate.trim() !== '' ? round2((subtotal * rate) / 100) : 0
  const total = round2(subtotal + tax)

  const problems: string[] = []
  if (!customer.trim()) problems.push('Add who the invoice is for.')
  if (filled.length === 0) problems.push('Add at least one line.')
  states.forEach((s, i) => {
    if (s.blank) return
    const n = i + 1
    if (!s.name) problems.push(`Line ${n} needs a description.`)
    if (!s.qtyOk) problems.push(`Line ${n} needs a whole-number quantity of 1 or more.`)
    if (!s.priceOk) problems.push(`Line ${n} needs a unit price of 0 or more.`)
  })
  if (!rateOk) problems.push('Tax rate must be between 0 and 100.')

  // The exact arguments the vendor's generate_invoice tool takes: customer_name and items[{name, amount, quantity}].
  const buildArgs = () => {
    const items = filled.map(({ s }) => ({ name: s.name, amount: round2(s.price), quantity: s.qty }))
    if (tax > 0) items.push({ name: `Tax at ${rate}%`, amount: tax, quantity: 1 })
    return { customer_name: customer.trim(), items }
  }

  const update = (key: number, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  const addRow = () => {
    const key = nextKey.current++
    setRows((rs) => [...rs, { key, name: '', quantity: '1', amount: '' }])
    requestAnimationFrame(() => nameRefs.current[key]?.focus())
  }
  const removeRow = (key: number) => {
    const idx = rows.findIndex((r) => r.key === key)
    setRows((rs) => rs.filter((r) => r.key !== key))
    const neighbour = rows[idx + 1] ?? rows[idx - 1]
    requestAnimationFrame(() => {
      if (neighbour) nameRefs.current[neighbour.key]?.focus()
    })
  }

  const done = Boolean(result) && props.resultTool === TOOL
  const failed = done && Boolean(result?.isError)
  const pdfPath = done && !failed ? (text.match(/\/[^\s'"]+\.pdf/) || [])[0] : undefined
  const showProblems = touched && problems.length > 0

  return (
    <div className="invoice_mcp">
      <form
        className="invoice_mcp__sheet"
        aria-labelledby="invoice_mcp-title"
        onSubmit={(e) => {
          e.preventDefault()
        }}
      >
        <header className="invoice_mcp__top">
          <h2 id="invoice_mcp-title" className="invoice_mcp__title">
            Invoice
          </h2>
          <p className="invoice_mcp__cur">Amounts in US dollars</p>
        </header>

        <div className="invoice_mcp__billto">
          <label className="invoice_mcp__lab" htmlFor="invoice_mcp-customer">
            Bill to
          </label>
          <input
            id="invoice_mcp-customer"
            className="invoice_mcp__in invoice_mcp__in--big"
            data-testid="field-customer_name"
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            placeholder="Customer or company name"
            autoComplete="organization"
            disabled={running}
          />
        </div>

        <div className="invoice_mcp__lines" data-testid="field-items" role="table" aria-label="Line items">
          <div className="invoice_mcp__row invoice_mcp__row--head" role="row">
            <span role="columnheader">Description</span>
            <span role="columnheader" className="num">Qty</span>
            <span role="columnheader" className="num">Unit price</span>
            <span role="columnheader" className="num">Amount</span>
            <span role="columnheader" className="invoice_mcp__sr">Remove</span>
          </div>
          {rows.map((r, i) => {
            const s = states[i]
            const n = i + 1
            return (
              <div className="invoice_mcp__row" role="row" key={r.key}>
                <span role="cell" className="invoice_mcp__cell invoice_mcp__cell--name">
                  <label className="invoice_mcp__mlab" htmlFor={`invoice_mcp-name-${r.key}`}>
                    Line {n} description
                  </label>
                  <input
                    id={`invoice_mcp-name-${r.key}`}
                    ref={(el) => {
                      nameRefs.current[r.key] = el
                    }}
                    className="invoice_mcp__in"
                    data-testid={`field-items-${i}-name`}
                    aria-label={`Line ${n} description`}
                    aria-invalid={touched && !s.blank && !s.name}
                    value={r.name}
                    placeholder="What you did or sold"
                    onChange={(e) => update(r.key, { name: e.target.value })}
                    disabled={running}
                  />
                </span>
                <span role="cell" className="invoice_mcp__cell num">
                  <label className="invoice_mcp__mlab" htmlFor={`invoice_mcp-qty-${r.key}`}>
                    Qty
                  </label>
                  <input
                    id={`invoice_mcp-qty-${r.key}`}
                    className="invoice_mcp__in num"
                    data-testid={`field-items-${i}-quantity`}
                    aria-label={`Line ${n} quantity`}
                    aria-invalid={touched && !s.blank && !s.qtyOk}
                    inputMode="numeric"
                    type="number"
                    min={1}
                    step={1}
                    value={r.quantity}
                    onChange={(e) => update(r.key, { quantity: e.target.value })}
                    disabled={running}
                  />
                </span>
                <span role="cell" className="invoice_mcp__cell num">
                  <label className="invoice_mcp__mlab" htmlFor={`invoice_mcp-amt-${r.key}`}>
                    Unit price
                  </label>
                  <input
                    id={`invoice_mcp-amt-${r.key}`}
                    className="invoice_mcp__in num"
                    data-testid={`field-items-${i}-amount`}
                    aria-label={`Line ${n} unit price in dollars`}
                    aria-invalid={touched && !s.blank && !s.priceOk}
                    inputMode="decimal"
                    type="number"
                    min={0}
                    step={0.01}
                    value={r.amount}
                    placeholder="0.00"
                    onChange={(e) => update(r.key, { amount: e.target.value })}
                    disabled={running}
                  />
                </span>
                <span role="cell" className="invoice_mcp__cell invoice_mcp__amt num">
                  <span className="invoice_mcp__mlab">Amount</span>
                  {usd.format(s.line)}
                </span>
                <span role="cell" className="invoice_mcp__cell invoice_mcp__rm">
                  <button
                    type="button"
                    className="invoice_mcp__x"
                    onClick={() => removeRow(r.key)}
                    disabled={running || rows.length === 1}
                    aria-label={`Remove line ${n}${r.name ? `, ${r.name}` : ''}`}
                  >
                    Remove
                  </button>
                </span>
              </div>
            )
          })}
        </div>
        <button type="button" className="invoice_mcp__add" onClick={addRow} disabled={running}>
          Add a line
        </button>

        <dl className="invoice_mcp__sum" aria-live="polite">
          <div>
            <dt>Subtotal</dt>
            <dd className="num">{usd.format(subtotal)}</dd>
          </div>
          <div className="invoice_mcp__taxrow">
            <dt>
              <label htmlFor="invoice_mcp-tax">Tax rate</label>
              <span className="invoice_mcp__taxin">
                <input
                  id="invoice_mcp-tax"
                  className="invoice_mcp__in num"
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={100}
                  step={0.1}
                  value={taxRate}
                  aria-invalid={!rateOk}
                  onChange={(e) => setTaxRate(e.target.value)}
                  disabled={running}
                />
                <span aria-hidden="true">%</span>
              </span>
            </dt>
            <dd className="num">{usd.format(tax)}</dd>
          </div>
          <div className="invoice_mcp__total">
            <dt>Total due</dt>
            <dd className="num" data-testid="invoice-total">
              {usd.format(total)}
            </dd>
          </div>
        </dl>
        <p className="invoice_mcp__fine">
          The printed invoice lists the customer, each line with its amount, {tax > 0 ? 'tax as its own line, ' : ''}and the total due.
        </p>
      </form>

      <div className="invoice_mcp__go">
        {showProblems && (
          <ul className="invoice_mcp__problems" role="alert">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        <PayButton
          label={invoiceLabel(props.payLabel)}
          runningLabel="Making the PDF. Waiting for the wallet and the service"
          running={running}
          disabled={!canRun || listing.online === false}
          onClick={() => {
            setTouched(true)
            if (problems.length) return
            run({ tool: TOOL, args: buildArgs() })
          }}
        />
      </div>

      {(done || running) && (
        <section className="invoice_mcp__out" aria-labelledby="invoice_mcp-out" aria-busy={running}>
          <h2 id="invoice_mcp-out" className="invoice_mcp__h">
            Your invoice
          </h2>
          {running && <p className="invoice_mcp__wait" role="status">Rendering the PDF</p>}
          {pdfPath && (
            <>
              <iframe className="invoice_mcp__pdf" src={getFileUrl(pdfPath)} title="Invoice PDF" />
              <p className="invoice_mcp__links">
                <a href={getFileUrl(pdfPath)} download={`invoice-${customer.trim().replace(/[^\w-]+/g, '-').toLowerCase() || 'customer'}.pdf`}>
                  Download the PDF
                </a>
                <a href={getFileUrl(pdfPath)} target="_blank" rel="noopener noreferrer">
                  Open in a new tab
                </a>
              </p>
            </>
          )}
          {failed && <p className="invoice_mcp__err">The service could not make the invoice. Its reason is below.</p>}
          {done && <RawOutput text={text} />}
        </section>
      )}
    </div>
  )
}

export default InvoiceBuilder
