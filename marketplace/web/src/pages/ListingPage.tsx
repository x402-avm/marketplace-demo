import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useWallet } from '@txnlab/use-wallet-react'
import { getListing, callListing, getConfig, getVendors } from '../api'
import type { ActivePass, Listing, ToolInfo, CallResponse, GatewayConfig } from '../types'
import { SchemaForm } from '../components/SchemaForm'
import { FilePreview } from '../components/FilePreview'
import { PassOffer } from '../components/PassOffer'
import { usePasses } from '../hooks/usePasses'
import { resolveAssetName } from '../utils/format'
import { payForRequirement, buildIdentityTxn, encodeIdentityHeader } from '../lib/payments'
import { passFor, serviceScope, vendorScope } from '../lib/passes'
import { domainInfo } from '../lib/domains'
import { vendorById } from '../lib/vendors'
import { money } from '../lib/catalog'
import { TOOL_UIS } from '../tools/registry'
import { PayButton, RawOutput } from '../tools/kit'
import type { RunOptions, ToolUIProps } from '../tools/kit'

const FILE_RE = /(?:'|")?(\/(?:[a-zA-Z0-9_\-.]+\/)+[a-zA-Z0-9_\-.]+\.(?:png|jpg|jpeg|webp|gif|svg|mp3|wav|ogg|mp4|webm|pdf|json|txt))(?:'|")?/g

function filePaths(text: string): string[] {
  const out: string[] = []
  for (const m of text.matchAll(FILE_RE)) if (!out.includes(m[1])) out.push(m[1])
  return out
}

export const ListingPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const { activeAddress, algodClient, signTransactions } = useWallet()
  const { passes, waitFor } = usePasses()

  const [listing, setListing] = useState<Listing | null>(null)
  const [config, setConfig] = useState<GatewayConfig | null>(null)
  const [toolName, setToolName] = useState('')
  const [args, setArgs] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<CallResponse | null>(null)
  const [usedPass, setUsedPass] = useState(false)
  const [resultTool, setResultTool] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    if (!id) return
    setLoading(true)
    Promise.all([getListing(id), getConfig().catch(() => null)])
      .then(([l, cfg]) => {
        if (!alive) return
        setListing(l)
        setConfig(cfg)
        setToolName(l.tools?.[0]?.name ?? '')
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [id])

  if (loading) return <div className="page state">Opening the service</div>
  if (!listing) {
    return (
      <div className="page">
        <p className="notice notice--error">{error ?? 'This service does not exist.'}</p>
        <p style={{ marginTop: 16 }}>
          <Link to="/">Back to the directory</Link>
        </p>
      </div>
    )
  }

  const identity = vendorById(listing.vendor.id)
  const tone = identity?.tone ?? 'nova'
  const info = domainInfo(listing.domain)
  const tool: ToolInfo | undefined = listing.tools?.find((t) => t.name === toolName)
  const pass = passFor(passes, listing)
  const servicePass = passes.find((p) => p.scope === serviceScope(listing))
  const vendorPass = passes.find((p) => p.scope === vendorScope(listing.vendor.id))

  const run = async (opts?: RunOptions) => {
    const name = opts?.tool ?? toolName
    const callArgs = opts?.args ?? args
    if (!id || !name || !activeAddress) return
    setRunning(true)
    setError(null)
    setResponse(null)
    setUsedPass(false)
    setResultTool(name)
    try {
      // A pass is proven with a signed, never-submitted, zero-fee transaction from the wallet.
      let identityTxn: string | undefined
      if (pass && config?.genesisHash) {
        const signed = await signTransactions([buildIdentityTxn(activeAddress, config.genesisHash)], [0])
        if (signed?.[0]) identityTxn = encodeIdentityHeader(signed[0])
      }
      const first = await callListing(id, { tool: name, args: callArgs, identityTxn })
      if (first.status !== 402) {
        setUsedPass(Boolean(identityTxn))
        setResponse(first)
        return
      }
      let paymentSignature: string
      try {
        paymentSignature = await payForRequirement(first.paymentRequired, activeAddress, algodClient, (t, i) => signTransactions(t, i))
      } catch (e: any) {
        setError(`The payment was not signed or could not be built: ${e.message || e}`)
        return
      }
      const paid = await callListing(id, { tool: name, args: callArgs, paymentSignature, identityTxn })
      if (paid.status !== 200) {
        setError('The vendor refused the payment. Check that this wallet has enough funds and try again.')
      } else {
        setResponse(paid)
      }
    } catch (e: any) {
      setError(String(e.message || e).replace(/^API error \(\d+\): /, ''))
    } finally {
      setRunning(false)
    }
  }

  const ok = response && response.status === 200 ? response : null
  const text = ok?.result?.content?.map((c) => c.text || JSON.stringify(c)).join('\n') ?? ''
  const files = filePaths(text)
  const priceOf = (name: string) => {
    const t = listing.tools?.find((x) => x.name === name)
    return t ? money(t.price, listing.asset) : ''
  }
  const label = tool ? (pass ? 'Run with your pass' : `Pay ${money(tool.price, listing.asset)} and run`) : 'Run'
  const selectTool = (name: string) => {
    setToolName(name)
    setArgs({})
    setResponse(null)
    setError(null)
  }
  const Custom = TOOL_UIS[listing.domain]
  const uiProps: ToolUIProps = {
    listing,
    tools: listing.tools ?? [],
    tool,
    selectTool,
    args,
    setArgs,
    run,
    running,
    result: ok?.result ?? null,
    resultTool,
    text,
    files,
    payLabel: label,
    priceOf,
    canRun: Boolean(activeAddress) && listing.online !== false,
  }

  return (
    <div className={`svc svc--${tone}`}>
      <div className="svc__inner">
        <nav className="svc__crumbs" aria-label="Breadcrumb">
          <Link to={`/vendors/${identity?.slug ?? ''}`}>{listing.vendor.name}</Link>
          <span aria-hidden="true">/</span>
          <span>{info.title}</span>
        </nav>

        <header className="svc__head">
          <h1 className="svc__title">{info.title}</h1>
          <p className="svc__summary">{info.summary}</p>
          <ul className="svc__facts">
            <li>{listing.online ? 'Running now' : 'Stopped right now'}</li>
            <li>Paid in {listing.asset}</li>
            <li>
              Service <span className="hash" data-testid="service-id">{listing.id}</span>
            </li>
          </ul>
        </header>

        <div className="svc__status" aria-live="polite">
          {!listing.online && <p className="svc__note">This vendor has stopped the service. Try another vendor from the directory.</p>}
          {!activeAddress && (
            <p className="svc__note">
              <Link to="/wallet">Connect a wallet</Link> to pay for a call.
            </p>
          )}
          {pass && (
            <p className="svc__note" data-testid="pass-active">
              Your {pass.kind === 'vendor' ? `${listing.vendor.name} pass` : 'pass for this service'} covers calls here.
            </p>
          )}
          {error && (
            <p className="svc__error" role="alert" data-testid="call-error">
              {error}
            </p>
          )}
          {ok &&
            (ok.result?.isError ? (
              <p className="svc__receipt svc__receipt--error" data-testid="not-charged">
                The tool returned an error, so you were not charged.
              </p>
            ) : ok.payment?.txid ? (
              <p className="svc__receipt" data-testid="paid-txid">
                Paid {money(ok.payment.amount, resolveAssetName(ok.payment.asset, config?.assets))} to {listing.vendor.name}.{' '}
                <Link to={`/explorer/tx/${ok.payment.txid}`}>Transaction {ok.payment.txid.slice(0, 10)}</Link>
              </p>
            ) : usedPass ? (
              <p className="svc__receipt" data-testid="covered-by-pass">
                Covered by your pass. Nothing was charged.
              </p>
            ) : null)}
        </div>

        {Custom ? (
          <section className="svc__work" aria-label={`${info.title} tool`}>
            <Custom {...uiProps} />
          </section>
        ) : (
          <GenericWorkbench {...uiProps} />
        )}

        <section className="svc__passes" aria-labelledby="passes-title">
          <h2 id="passes-title" className="svc__h2">Passes</h2>
          <p className="svc__passintro">
            A pass makes calls free for 30 days. It is paid to {listing.vendor.name} and works only with {listing.vendor.name}.
          </p>
          <div className="svc__offers">
            {listing.pass && (
              <PassOffer
                scope={serviceScope(listing)}
                title="This service"
                detail={`${info.title} from ${listing.vendor.name}, any tool, for 30 days.`}
                price={listing.pass.price}
                asset={listing.asset}
                active={servicePass}
                onBought={waitFor}
                testid="service-pass"
              />
            )}
            <VendorPassOffer listing={listing} active={vendorPass} onBought={waitFor} />
          </div>
        </section>
      </div>
    </div>
  )
}

/** The vendor-wide pass; its price comes from the vendor record. */
const VendorPassOffer: React.FC<{ listing: Listing; active?: ActivePass; onBought: (t: string) => Promise<unknown> }> = ({
  listing,
  active,
  onBought,
}) => {
  const [price, setPrice] = useState<number | null>(null)
  useEffect(() => {
    getVendors()
      .then((vs) => setPrice(vs.find((v) => v.id === listing.vendor.id)?.pass?.price ?? null))
      .catch(() => setPrice(null))
  }, [listing.vendor.id])
  if (price === null) return null
  return (
    <PassOffer
      scope={vendorScope(listing.vendor.id)}
      title={`Everything from ${listing.vendor.name}`}
      detail={`Every ${listing.vendor.name} service for 30 days.`}
      price={price}
      asset={listing.asset}
      active={active}
      onBought={onBought}
      testid="vendor-pass"
    />
  )
}

/** The fallback for services without their own interface: a form generated from the tool's input schema. */
const GenericWorkbench: React.FC<ToolUIProps> = ({ listing, tools, tool, selectTool, args, setArgs, run, running, result, text, files, payLabel, priceOf, canRun }) => (
  <div className="svc__grid">
    <section className="svc__panel svc__run" aria-labelledby="run-title">
      <h2 id="run-title" className="svc__h2">Run it</h2>
      <div className="field">
        <label className="field__label" htmlFor="tool-select">Tool</label>
        <select id="tool-select" data-testid="tool-select" className="input" value={tool?.name ?? ''} onChange={(e) => selectTool(e.target.value)}>
          {tools.map((t) => (
            <option key={t.name} value={t.name}>
              {t.name.replace(/_/g, ' ')}, {priceOf(t.name)}
            </option>
          ))}
        </select>
        {tool?.description && <span className="field__hint">{tool.description}</span>}
      </div>
      {tool && <SchemaForm schema={tool.inputSchema} value={args} onChange={setArgs} disabled={running} />}
      <div className="svc__action">
        <PayButton label={payLabel} running={running} disabled={!canRun || !tool || listing.online === false} onClick={() => run()} />
      </div>
    </section>
    <section className="svc__panel svc__out" aria-labelledby="out-title">
      <h2 id="out-title" className="svc__h2">Result</h2>
      {!result && !running && <p className="svc__empty">Fill in the form and run the tool. The output appears here.</p>}
      {running && <p className="svc__empty">Running. Payment settles only if the tool succeeds.</p>}
      {result && (
        <>
          <RawOutput text={text} />
          {files.map((p) => (
            <FilePreview key={p} path={p} />
          ))}
        </>
      )}
    </section>
  </div>
)
