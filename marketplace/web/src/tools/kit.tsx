/**
 * Contract for per-service tool interfaces.
 *
 * Each service domain may provide its own interface in src/tools/<domain>/index.tsx:
 *
 *   export const domain = 'tts'
 *   const TtsStudio: React.FC<ToolUIProps> = (props) => ...
 *   export default TtsStudio
 *
 * The service page (pages/ListingPage.tsx) owns everything around it: the vendor header, payment, passes,
 * the "Paid ... / not charged / covered by your pass" receipt and error messages. The tool interface owns only
 * the inputs and how the output is shown.
 *
 * Rules every interface must follow (the end-to-end tests rely on them):
 *  - Start a call ONLY through props.run(...). It signs the payment (or a pass identity proof) and calls the service.
 *  - The main action button is <PayButton/> (data-testid="pay-run").
 *  - After a result, render <RawOutput text={props.text}/> (data-testid="result-text") somewhere visible.
 *  - Give every input a data-testid="field-<argument name>" (e.g. field-text, field-code, field-language).
 *  - Style with the vendor tokens (--s-bg, --s-ink, --s-muted, --s-accent, --s-panel, --s-rule, --s-display,
 *    --s-body, --s-panel-radius, --s-btn-*, --s-field-bg, --s-field-border) so the tool looks right in all four
 *    storefront identities. Never hard-code a vendor colour.
 */
import React, { useRef, useState } from 'react'
import type { CallResult, Listing, ToolInfo } from '../types'
import { uploadFile } from '../api'

export { FilePreview } from '../components/FilePreview'
export { getFileUrl } from '../api'

export interface RunOptions {
  /** tool to call; defaults to the selected tool */
  tool?: string
  /** arguments to send; defaults to props.args */
  args?: Record<string, any>
}

export interface ToolUIProps {
  listing: Listing
  /** every tool this service offers, with input schema and price */
  tools: ToolInfo[]
  /** the selected tool */
  tool: ToolInfo | undefined
  selectTool: (name: string) => void
  /** arguments for the selected tool (kept by the page so they survive re-renders) */
  args: Record<string, any>
  setArgs: (args: Record<string, any>) => void
  /** pay (or use a pass) and call the service; resolves when the result or an error is shown */
  run: (opts?: RunOptions) => Promise<void>
  running: boolean
  /** last result from the service (may be isError), null before the first call */
  result: CallResult | null
  /** name of the tool that produced `result` */
  resultTool: string | null
  /** all text content of the result joined with newlines */
  text: string
  /** absolute server paths of files found in the result text (images, audio, video, pdf, json, txt) */
  files: string[]
  /** "Pay 0.02 ALGO and run" or "Run with your pass" for the selected tool */
  payLabel: string
  /** price label for any tool name, e.g. "0.02 ALGO" */
  priceOf: (toolName: string) => string
  /** false when no wallet is connected or the service is stopped */
  canRun: boolean
}

export const PayButton: React.FC<{ label: string; running: boolean; disabled?: boolean; onClick: () => void; runningLabel?: string }> = ({
  label,
  running,
  disabled,
  onClick,
  runningLabel,
}) => (
  <button type="button" className="svc__pay" data-testid="pay-run" disabled={running || disabled} onClick={onClick}>
    {running ? runningLabel ?? 'Waiting for the wallet and the service' : label}
  </button>
)

/** The service's own words, unformatted. Always shown after a call. */
export const RawOutput: React.FC<{ text: string; title?: string }> = ({ text, title = 'Response' }) => (
  <div className="rawout">
    <p className="rawout__title">{title}</p>
    <pre className="rawout__text" data-testid="result-text">
      {text || 'The tool returned no text.'}
    </pre>
  </div>
)

/** Upload a local file to the gateway; calls onPath with the server path the tools accept. */
export const UploadButton: React.FC<{ onPath: (path: string, file: File) => void; accept?: string; label?: string; testid?: string }> = ({
  onPath,
  accept,
  label = 'Choose a file',
  testid,
}) => {
  const ref = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <span className="upload">
      <input
        ref={ref}
        type="file"
        accept={accept}
        hidden
        onChange={async (e) => {
          const f = e.target.files?.[0]
          if (!f) return
          setBusy(true)
          setError(null)
          try {
            const { path } = await uploadFile(f)
            onPath(path, f)
          } catch (err: any) {
            setError(String(err.message || err))
          } finally {
            setBusy(false)
            e.target.value = ''
          }
        }}
      />
      <button type="button" className="btn btn--quiet" data-testid={testid} disabled={busy} onClick={() => ref.current?.click()}>
        {busy ? 'Uploading' : label}
      </button>
      {error && <span className="upload__error">{error}</span>}
    </span>
  )
}

/** Try to read the result text as JSON (many services answer with JSON). */
export function parseJson<T = any>(text: string): T | null {
  const t = text.trim()
  if (!t || (t[0] !== '{' && t[0] !== '[')) return null
  try {
    return JSON.parse(t) as T
  } catch {
    return null
  }
}

export function fileName(path: string): string {
  return path.split('/').pop() || path
}
