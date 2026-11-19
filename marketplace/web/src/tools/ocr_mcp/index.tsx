import React, { useEffect, useMemo, useRef, useState } from 'react'
import { PayButton, RawOutput, UploadButton, getFileUrl, fileName, parseJson } from '../kit'
import type { ToolUIProps } from '../kit'
import './ocr_mcp.css'

export const domain = 'ocr_mcp'

type Accepts = 'image' | 'pdf' | 'both'

interface Kind {
  tool: string
  arg: string
  name: string
  detail: string
  accepts: Accepts
  action: string
}

/** The service's reading tools, named by what the person is holding. */
const KINDS: Kind[] = [
  { tool: 'image_to_text', arg: 'image_url', name: 'Printed text', detail: 'A photo or scan of typed words', accepts: 'image', action: 'Read the text' },
  { tool: 'receipt_ocr', arg: 'image_url', name: 'A receipt', detail: 'Shop name, each item and the total', accepts: 'image', action: 'Read the receipt' },
  { tool: 'table_extraction', arg: 'image_or_pdf_url', name: 'A table', detail: 'Rows and columns, from a picture or a PDF', accepts: 'both', action: 'Pull out the table' },
  { tool: 'handwriting_ocr', arg: 'image_url', name: 'Handwriting', detail: 'Clear handwritten notes', accepts: 'image', action: 'Read the handwriting' },
  { tool: 'math_ocr', arg: 'image_url', name: 'Maths', detail: 'An equation, written out as LaTeX', accepts: 'image', action: 'Read the maths' },
  { tool: 'barcode_reader', arg: 'image_url', name: 'A barcode or QR code', detail: 'The value each code holds', accepts: 'image', action: 'Read the codes' },
  { tool: 'pdf_to_text', arg: 'pdf_url', name: 'A PDF', detail: 'All of its text, page by page', accepts: 'pdf', action: 'Read the PDF' },
]

interface Doc {
  path: string
  name: string
  isPdf: boolean
  url: string
}

const isPdfPath = (p: string) => /\.pdf$/i.test(p)

function fits(kind: Kind, doc: Doc | null): boolean {
  if (!doc) return true
  if (kind.accepts === 'both') return true
  return doc.isPdf ? kind.accepts === 'pdf' : kind.accepts === 'image'
}

const OcrDesk: React.FC<ToolUIProps> = ({ tools, run, running, result, resultTool, text, priceOf, payLabel, canRun, listing }) => {
  const kinds = useMemo(() => KINDS.filter((k) => tools.some((t) => t.name === k.tool)), [tools])
  const [doc, setDoc] = useState<Doc | null>(null)
  const [kindName, setKindName] = useState('image_to_text')
  const [pathInput, setPathInput] = useState('')
  const [readFrom, setReadFrom] = useState<Doc | null>(null)
  const localUrl = useRef<string | null>(null)

  const kind = kinds.find((k) => k.tool === kindName) ?? kinds[0]
  const usePass = payLabel.startsWith('Run with')

  const choose = (path: string, name: string, url?: string) => {
    const pdf = isPdfPath(name) || isPdfPath(path)
    const next: Doc = { path, name, isPdf: pdf, url: url ?? getFileUrl(path) }
    setDoc(next)
    setPathInput(path)
    const current = kinds.find((k) => k.tool === kindName)
    if (current && !fits(current, next)) setKindName(pdf ? 'pdf_to_text' : 'image_to_text')
  }

  useEffect(
    () => () => {
      if (localUrl.current) URL.revokeObjectURL(localUrl.current)
    },
    [],
  )

  const start = () => {
    if (!doc || !kind) return
    setReadFrom(doc)
    run({ tool: kind.tool, args: { [kind.arg]: doc.path } })
  }

  const ready = Boolean(doc && kind && fits(kind, doc))
  const label = kind ? `${kind.action}, ${usePass ? 'with your pass' : `pay ${priceOf(kind.tool)}`}` : 'Read'
  const shownDoc = readFrom && result ? readFrom : doc
  const ranKind = KINDS.find((k) => k.tool === resultTool)

  return (
    <div className="ocr">
      <section className="ocr__source" aria-labelledby="ocr-source-h">
        <div className="ocr__pick">
          <h2 id="ocr-source-h" className="svc__h2 ocr__h">
            The document
          </h2>
          <UploadButton
            accept="image/png,image/jpeg,image/webp,application/pdf"
            label={doc ? 'Choose another file' : 'Choose an image or PDF'}
            testid="upload-document"
            onPath={(path, file) => {
              if (localUrl.current) URL.revokeObjectURL(localUrl.current)
              localUrl.current = URL.createObjectURL(file)
              choose(path, file.name, localUrl.current)
            }}
          />
        </div>
        {shownDoc ? (
          <div className="ocr__paper">
            {shownDoc.isPdf ? (
              <>
                <iframe src={shownDoc.url} className="ocr__pdf" title={`Preview of ${shownDoc.name}`} />
                <p className="ocr__muted">
                  <a href={shownDoc.url} target="_blank" rel="noopener noreferrer">
                    Open {shownDoc.name}
                  </a>
                </p>
              </>
            ) : (
              <img src={shownDoc.url} alt={`The document you chose, ${shownDoc.name}`} className="ocr__img" />
            )}
            <p className="ocr__fname">{shownDoc.name}</p>
          </div>
        ) : (
          <p className="ocr__muted ocr__empty">
            Take a photo or scan of a receipt, a table, a note, an equation or a QR code, or pick a PDF. It shows here, and the reading appears beside it.
          </p>
        )}
        <details className="ocr__path">
          <summary>Use a file already on the server, or a web link</summary>
          <div className="ocr__pathrow">
            <label className="visually-hidden" htmlFor="ocr-path">
              Server path or link to the document
            </label>
            <input
              id="ocr-path"
              className="input"
              data-testid={`field-${kind?.arg ?? 'image_url'}`}
              value={pathInput}
              placeholder="/path/to/scan.png or https://"
              onChange={(e) => setPathInput(e.target.value)}
            />
            <button type="button" className="ocr__btn" disabled={!pathInput.trim()} onClick={() => choose(pathInput.trim(), fileName(pathInput.trim()))}>
              Use it
            </button>
          </div>
        </details>
      </section>

      <div className="ocr__side">
        <fieldset className="ocr__kinds" disabled={running}>
          <legend className="svc__h2 ocr__h">What is it?</legend>
          <div className="ocr__kindlist">
            {kinds.map((k) => {
              const ok = fits(k, doc)
              return (
                <label key={k.tool} className={`ocr__kind${k.tool === kind?.tool ? ' is-on' : ''}${ok ? '' : ' is-off'}`} data-testid={`ocr-kind-${k.tool}`}>
                  <input
                    type="radio"
                    name="ocr-kind"
                    value={k.tool}
                    checked={k.tool === kind?.tool}
                    disabled={!ok}
                    onChange={() => setKindName(k.tool)}
                  />
                  <span className="ocr__kindname">{k.name}</span>
                  <span className="ocr__kindprice">{priceOf(k.tool)}</span>
                  <span className="ocr__kinddetail">{ok ? k.detail : doc?.isPdf ? 'Needs an image, not a PDF' : 'Needs a PDF'}</span>
                </label>
              )
            })}
          </div>
        </fieldset>

        <div className="ocr__go">
          <PayButton label={label} running={running} runningLabel="Reading the document" disabled={!canRun || !ready || listing.online === false} onClick={start} />
          {!doc && <p className="ocr__muted">Choose a file first.</p>}
        </div>

        <section className="ocr__reading" aria-live="polite" aria-labelledby="ocr-reading-h">
          <h2 id="ocr-reading-h" className="svc__h2 ocr__h">
            {ranKind && result && !running ? `Reading: ${ranKind.name.replace(/^An? /, '').toLowerCase()}` : 'Reading'}
          </h2>
          {running && <p className="ocr__muted">Reading the document. You pay only if text comes back.</p>}
          {!running && !result && <p className="ocr__muted">The text, table, equation or code values will appear here.</p>}
          {!running && result?.isError && (
            <p className="ocr__error" role="alert">
              The service could not read this as {ranKind?.name.toLowerCase() ?? 'a document'}. It said: {text || 'nothing'}
            </p>
          )}
          {!running && result && !result.isError && <Reading tool={resultTool ?? ''} text={text} />}
          {!running && result && <RawOutput text={text} title="What the service sent back" />}
        </section>
      </div>
    </div>
  )
}

/* ------------------------------ output views ------------------------------ */

const CopyButton: React.FC<{ value: string; label?: string }> = ({ value, label = 'Copy' }) => {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      className="ocr__btn ocr__copy"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value)
          setDone(true)
          setTimeout(() => setDone(false), 1600)
        } catch {
          setDone(false)
        }
      }}
    >
      <span aria-live="polite">{done ? 'Copied' : label}</span>
    </button>
  )
}

const Reading: React.FC<{ tool: string; text: string }> = ({ tool, text }) => {
  const json = parseJson<any>(text)
  if (tool === 'table_extraction' && json && Array.isArray(json.rows)) return <TableView rows={json.rows} />
  if (tool === 'receipt_ocr' && json && typeof json === 'object' && !Array.isArray(json)) return <ReceiptView r={json} />
  if (tool === 'barcode_reader' && Array.isArray(json)) return <CodesView codes={json} />
  if (tool === 'math_ocr') return <MathView text={text} />
  if (tool === 'pdf_to_text') return <PagesView text={text} />
  return <PlainView text={text} />
}

const PlainView: React.FC<{ text: string }> = ({ text }) => {
  const lines = text.split('\n')
  const note = lines[0]?.startsWith('Note:') ? lines[0].replace(/^Note:\s*/, '') : null
  const body = (note ? lines.slice(1) : lines).join('\n').trim()
  return (
    <div className="ocr__plain">
      {note && <p className="ocr__muted ocr__note">{note}</p>}
      <div className="ocr__textbox">
        <p className="ocr__text" data-testid="ocr-text">
          {body || 'No text was found.'}
        </p>
        {body && <CopyButton value={body} label="Copy text" />}
      </div>
    </div>
  )
}

const PagesView: React.FC<{ text: string }> = ({ text }) => {
  const parts = text.split(/^--- page (\d+) ---$/m)
  const pages: { n: string; body: string }[] = []
  for (let i = 1; i < parts.length; i += 2) pages.push({ n: parts[i], body: (parts[i + 1] ?? '').trim() })
  if (!pages.length) return <PlainView text={text} />
  const all = pages.map((p) => p.body).join('\n\n')
  return (
    <div className="ocr__pages">
      <div className="ocr__rowhead">
        <p className="ocr__muted">
          {pages.length} {pages.length === 1 ? 'page' : 'pages'}
        </p>
        <CopyButton value={all} label="Copy all text" />
      </div>
      {pages.map((p) => (
        <article key={p.n} className="ocr__page" aria-label={`Page ${p.n}`}>
          <p className="ocr__pageno">Page {p.n}</p>
          <p className="ocr__text">{p.body || 'No text on this page.'}</p>
        </article>
      ))}
    </div>
  )
}

const TableView: React.FC<{ rows: any[][] }> = ({ rows }) => {
  const clean = rows.filter((r) => Array.isArray(r)).map((r) => r.map((c) => String(c ?? '')))
  if (!clean.length) return <p className="ocr__muted">No table was found in this document.</p>
  const width = Math.max(...clean.map((r) => r.length))
  const [head, ...body] = clean
  const hasHeader = clean.length > 1 && width > 1
  const tsv = clean.map((r) => r.join('\t')).join('\n')
  const csv = clean.map((r) => r.map((c) => (/[",\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join(',')).join('\n')
  return (
    <div className="ocr__tablewrap">
      <div className="ocr__rowhead">
        <p className="ocr__muted">
          {clean.length} {clean.length === 1 ? 'row' : 'rows'}, {width} {width === 1 ? 'column' : 'columns'}
        </p>
        <span className="ocr__copies">
          <CopyButton value={tsv} label="Copy for a spreadsheet" />
          <CopyButton value={csv} label="Copy as CSV" />
        </span>
      </div>
      <div className="ocr__scroll" tabIndex={0} aria-label="Extracted table">
        <table className="ocr__table" data-testid="ocr-table">
          {hasHeader && (
            <thead>
              <tr>
                {Array.from({ length: width }, (_, i) => (
                  <th key={i} scope="col">
                    {head[i] ?? ''}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {(hasHeader ? body : clean).map((r, ri) => (
              <tr key={ri}>
                {Array.from({ length: width }, (_, i) => (
                  <td key={i} className={/^[-+]?[\d.,]+%?$/.test(r[i] ?? '') ? 'is-num' : undefined}>
                    {r[i] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const money = (n: any) => (typeof n === 'number' ? n.toFixed(2) : String(n ?? ''))

const ReceiptView: React.FC<{ r: any }> = ({ r }) => {
  const items: { name: string; price: any }[] = Array.isArray(r.items) ? r.items : []
  return (
    <div className="ocr__receipt" data-testid="ocr-receipt">
      <p className="ocr__merchant">{r.merchant || 'Shop name not found'}</p>
      {items.length > 0 ? (
        <table className="ocr__lines">
          <caption className="visually-hidden">Items on the receipt</caption>
          <tbody>
            {items.map((it, i) => (
              <tr key={i}>
                <th scope="row">{it.name}</th>
                <td>{money(it.price)}</td>
              </tr>
            ))}
          </tbody>
          {r.total !== undefined && r.total !== null && (
            <tfoot>
              <tr>
                <th scope="row">Total</th>
                <td>{money(r.total)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      ) : (
        <p className="ocr__muted">No separate items were found.{r.total != null ? ` Total ${money(r.total)}.` : ''}</p>
      )}
      {r.raw_text && (
        <details className="ocr__rawtext">
          <summary>Text as read from the receipt</summary>
          <p className="ocr__text">{r.raw_text}</p>
        </details>
      )}
    </div>
  )
}

const CodesView: React.FC<{ codes: any[] }> = ({ codes }) => {
  if (!codes.length) return <p className="ocr__muted">No barcode or QR code was found. Try a sharper, closer picture.</p>
  return (
    <ol className="ocr__codes" data-testid="ocr-codes">
      {codes.map((c, i) => {
        const value = String(c?.text ?? c?.data ?? c ?? '')
        const isLink = /^https?:\/\//i.test(value)
        return (
          <li key={i} className="ocr__code">
            <span className="ocr__codefmt">{c?.format ?? c?.type ?? 'Code'}</span>
            {isLink ? (
              <a className="ocr__codeval" href={value} target="_blank" rel="noopener noreferrer">
                {value}
              </a>
            ) : (
              <span className="ocr__codeval">{value}</span>
            )}
            <CopyButton value={value} />
          </li>
        )
      })}
    </ol>
  )
}

const MathView: React.FC<{ text: string }> = ({ text }) => {
  const latex = text.match(/^LaTeX:\s*(.*)$/m)?.[1]?.trim() ?? ''
  const plain = text.match(/^Text:\s*(.*)$/m)?.[1]?.trim() ?? ''
  if (!latex) return <PlainView text={text} />
  return (
    <div className="ocr__math" data-testid="ocr-math">
      <p className="ocr__mathlabel">LaTeX source</p>
      <div className="ocr__latexrow">
        <code className="ocr__latex">{latex}</code>
        <CopyButton value={latex} label="Copy LaTeX" />
      </div>
      <div className="ocr__latexrow">
        <code className="ocr__latex ocr__latex--inline">{`$${latex}$`}</code>
        <CopyButton value={`$${latex}$`} label="Copy with dollar signs" />
      </div>
      {plain && <p className="ocr__muted ocr__plainmath">Read as plain characters: {plain}</p>}
    </div>
  )
}

export default OcrDesk
