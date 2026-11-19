import React, { useEffect, useId, useMemo, useRef, useState } from 'react'
import { PayButton, RawOutput, UploadButton, getFileUrl, fileName } from '../kit'
import type { ToolUIProps } from '../kit'
import { ARCHIVE_FORMATS, ARCHIVE_NAMES, extOf, kindOf, nameOf, targetsFor, zipEntries } from './formats'
import type { Target } from './formats'
import './conversion_mcp.css'

export const domain = 'conversion_mcp'

type Mode = 'convert' | 'pack' | 'unpack'

interface Picked {
  path: string
  name: string
  ext: string
  entries?: string[] | null
}

interface Sent {
  mode: Mode
  from: string
  to: string
  tool: string
  entries: string[] | null
  count: number
}

const IMG = /^(png|jpe?g|webp|gif|bmp|tiff?)$/
const AUD = /^(mp3|wav|ogg|flac|m4a|aac)$/
const VID = /^(mp4|webm|mkv|mov)$/

/** Small CSV reader, enough to show a table: quoted fields and doubled quotes. */
function parseCsv(src: string, maxRows: number): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let q = false
  for (let i = 0; i < src.length && rows.length <= maxRows; i++) {
    const c = src[i]
    if (q) {
      if (c === '"' && src[i + 1] === '"') {
        cell += '"'
        i++
      } else if (c === '"') q = false
      else cell += c
    } else if (c === '"') q = true
    else if (c === ',') {
      row.push(cell)
      cell = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && src[i + 1] === '\n') i++
      row.push(cell)
      rows.push(row)
      row = []
      cell = ''
    } else cell += c
  }
  if (cell || row.length) {
    row.push(cell)
    rows.push(row)
  }
  return rows.filter((r) => r.some((c) => c !== ''))
}

const TextPreview: React.FC<{ url: string; ext: string }> = ({ url, ext }) => {
  const [body, setBody] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let live = true
    setBody(null)
    setFailed(false)
    fetch(url)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => live && setBody(t.slice(0, 60000)))
      .catch(() => live && setFailed(true))
    return () => {
      live = false
    }
  }, [url])
  const rows = useMemo(() => (body !== null && ext === 'csv' ? parseCsv(body, 12) : null), [body, ext])
  if (failed) return <p className="cnv-muted">The browser could not load a preview. Use the download link.</p>
  if (body === null) return <p className="cnv-muted">Loading preview</p>
  if (rows && rows.length) {
    const [head, ...rest] = rows
    return (
      <div className="cnv-tablewrap" tabIndex={0} role="region" aria-label="Preview of the converted table">
        <table className="cnv-table">
          <thead>
            <tr>
              {head.map((h, i) => (
                <th key={i} scope="col">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rest.slice(0, 11).map((r, i) => (
              <tr key={i}>
                {head.map((_, j) => (
                  <td key={j}>{r[j] ?? ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rest.length > 11 && <p className="cnv-muted cnv-more">The first rows only. The download holds all of them.</p>}
      </div>
    )
  }
  let shown = body
  if (ext === 'json') {
    try {
      shown = JSON.stringify(JSON.parse(body), null, 2)
    } catch {
      shown = body
    }
  }
  return (
    <pre className="cnv-pre" tabIndex={0} aria-label="Preview of the converted file">
      {shown.split('\n').slice(0, 40).join('\n')}
    </pre>
  )
}

const Preview: React.FC<{ url: string; ext: string; name: string }> = ({ url, ext, name }) => {
  if (IMG.test(ext)) return <img className="cnv-media" src={url} alt={`Preview of ${name}`} />
  if (AUD.test(ext)) return <audio className="cnv-audio" controls src={url} aria-label={`Play ${name}`} />
  if (VID.test(ext)) return <video className="cnv-media" controls src={url} aria-label={`Play ${name}`} />
  if (ext === 'pdf') return <iframe className="cnv-pdf" src={url} title={`Preview of ${name}`} />
  if (/^(csv|json|txt|md|html)$/.test(ext)) return <TextPreview url={url} ext={ext} />
  return null
}

const Delivered: React.FC<{ path: string; sent: Sent }> = ({ path, sent }) => {
  const ext = extOf(path)
  const name = fileName(path)
  const url = getFileUrl(path)
  if (sent.mode === 'unpack') {
    return (
      <div className="cnv-done">
        <h3 className="cnv-h3">Archive opened</h3>
        <p className="cnv-muted">The files were unpacked on the service, into {fileName(path)}.</p>
        {sent.entries && sent.entries.length > 0 ? (
          <ul className="cnv-entries" data-testid="cnv-unpacked">
            {sent.entries.map((e) => (
              <li key={e}>
                <span className="cnv-entries__name">{e}</span>
                <a href={getFileUrl(`${path}/${e}`)} target="_blank" rel="noopener noreferrer">
                  Open
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="cnv-muted">The service does not list what it unpacked. The folder is {path}.</p>
        )}
      </div>
    )
  }
  return (
    <div className="cnv-done">
      <header className="cnv-done__head">
        <div className="cnv-done__what">
          <h3 className="cnv-h3">{sent.mode === 'pack' ? `${sent.count} files packed` : `Converted to ${nameOf(sent.to)}`}</h3>
          <p className="cnv-muted">{name}</p>
        </div>
        <a className="cnv-dl" href={url} target="_blank" rel="noopener noreferrer" data-testid="cnv-download">
          Download {name}
        </a>
      </header>
      <Preview url={url} ext={ext} name={name} />
    </div>
  )
}

const Convert: React.FC<ToolUIProps> = (props) => {
  const { running, result, text, canRun, priceOf, payLabel } = props
  const uid = useId()
  const [mode, setMode] = useState<Mode>('convert')
  const [file, setFile] = useState<Picked | null>(null)
  const [pathInput, setPathInput] = useState('')
  const [stack, setStack] = useState<Picked[]>([])
  const [to, setTo] = useState<string>('')
  const [archiveFmt, setArchiveFmt] = useState('zip')
  const sent = useRef<Sent | null>(null)

  const withPass = payLabel.startsWith('Run with')
  const targets = useMemo<Target[]>(() => (file ? targetsFor(file.ext) : []), [file])
  const chosen = targets.find((t) => `${t.tool}:${t.to}` === to)
  const known = !!file && !!kindOf(file.ext)

  const unpackExt = file?.ext ?? ''
  const unpackOk = ARCHIVE_FORMATS.includes(unpackExt)

  useEffect(() => {
    if (!targets.some((t) => `${t.tool}:${t.to}` === to)) setTo('')
  }, [targets, to])

  const choose = async (path: string, name: string, f?: File) => {
    const picked: Picked = { path, name, ext: extOf(name) || extOf(path) }
    if (f && picked.ext === 'zip') picked.entries = await zipEntries(f)
    return picked
  }

  const tool = mode === 'convert' ? chosen?.tool ?? 'document_convert' : mode === 'pack' ? 'archive_create' : 'archive_extract'
  const ready = !running && canRun && (mode === 'convert' ? !!file && !!chosen : mode === 'pack' ? stack.length > 0 : !!file && unpackOk)

  const label = withPass
    ? mode === 'convert'
      ? chosen
        ? `Convert to ${chosen.to.toUpperCase()} with your pass`
        : 'Convert with your pass'
      : mode === 'pack'
        ? 'Pack the files with your pass'
        : 'Unpack with your pass'
    : mode === 'convert'
      ? chosen
        ? `Pay ${priceOf(tool)} and convert to ${chosen.to.toUpperCase()}`
        : `Pay ${priceOf('document_convert')} and convert`
      : mode === 'pack'
        ? `Pay ${priceOf('archive_create')} and pack ${stack.length || ''} ${stack.length === 1 ? 'file' : 'files'}`.replace('  ', ' ')
        : `Pay ${priceOf('archive_extract')} and unpack`

  const go = () => {
    if (mode === 'convert' && file && chosen) {
      sent.current = { mode, from: file.ext, to: chosen.to, tool: chosen.tool, entries: null, count: 1 }
      props.run({ tool: chosen.tool, args: { file_url: file.path, from_format: file.ext, to_format: chosen.to } })
    } else if (mode === 'pack') {
      sent.current = { mode, from: '', to: archiveFmt, tool: 'archive_create', entries: null, count: stack.length }
      props.run({ tool: 'archive_create', args: { file_urls: stack.map((s) => s.path), format: archiveFmt } })
    } else if (mode === 'unpack' && file) {
      sent.current = { mode, from: file.ext, to: '', tool: 'archive_extract', entries: file.entries ?? null, count: 1 }
      props.run({ tool: 'archive_extract', args: { file_url: file.path, format: file.ext } })
    }
  }

  const outPath = result && !result.isError ? text.trim().split('\n')[0].trim() : ''
  const modes: [Mode, string][] = [
    ['convert', 'Convert a file'],
    ['pack', 'Pack files into an archive'],
    ['unpack', 'Unpack an archive'],
  ]

  const upload = (
    <UploadButton
      testid="cnv-upload"
      label={file ? 'Choose another file' : mode === 'unpack' ? 'Choose an archive' : 'Choose a file'}
      accept={mode === 'unpack' ? '.zip,.tar,.gz,.tgz,.7z' : undefined}
      onPath={async (p, f) => {
        setFile(await choose(p, f.name, f))
        setPathInput(p)
      }}
    />
  )

  return (
    <div className="cnv">
      <div className="cnv-modes" role="radiogroup" aria-label="What to do">
        {modes.map(([m, name]) => (
          <label key={m} className={`cnv-modes__opt${mode === m ? ' is-on' : ''}`}>
            <input type="radio" name={`${uid}-mode`} checked={mode === m} onChange={() => setMode(m)} />
            <span>{name}</span>
          </label>
        ))}
      </div>

      <section className="cnv-in" aria-label={modes.find((m) => m[0] === mode)?.[1]}>
        {mode !== 'pack' && (
          <>
            <div className="cnv-source">
              <div className="cnv-stamp" aria-hidden="true">
                {file?.ext ? file.ext.toUpperCase() : '?'}
              </div>
              <div className="cnv-source__what">
                {file ? (
                  <>
                    <p className="cnv-source__name">{file.name}</p>
                    <p className="cnv-muted" data-testid="field-from_format">
                      {mode === 'unpack'
                        ? unpackOk
                          ? `${file.ext} archive`
                          : 'Not an archive the service can open'
                        : known
                          ? `${nameOf(file.ext)}${targets.length ? '' : ', nothing to convert it to'}`
                          : 'Type not supported by this service'}
                    </p>
                  </>
                ) : (
                  <p className="cnv-muted">
                    {mode === 'unpack' ? 'Choose a zip, tar, tar.gz or 7z file.' : 'Choose a file. Its type decides which formats you can convert it to.'}
                  </p>
                )}
                {upload}
              </div>
            </div>
            <div className="cnv-path">
              <label className="field__label" htmlFor={`${uid}-path`}>
                Or a file path on the service
              </label>
              <input
                id={`${uid}-path`}
                className="input"
                data-testid="field-file_url"
                value={pathInput}
                spellCheck={false}
                placeholder="/path/to/file"
                onChange={(e) => {
                  setPathInput(e.target.value)
                  const p = e.target.value.trim()
                  setFile(p ? { path: p, name: fileName(p), ext: extOf(p) } : null)
                }}
              />
            </div>
          </>
        )}

        {mode === 'convert' && file && known && targets.length > 0 && (
          <fieldset className="cnv-targets">
            <legend className="field__label">Convert to</legend>
            <div className="cnv-targets__grid" data-testid="field-to_format">
              {targets.map((t) => {
                const id = `${t.tool}:${t.to}`
                return (
                  <label key={id} className={`cnv-target${to === id ? ' is-on' : ''}`}>
                    <input type="radio" name={`${uid}-to`} checked={to === id} onChange={() => setTo(id)} />
                    <span className="cnv-target__ext">{t.to}</span>
                    <span className="cnv-target__name">{nameOf(t.to)}</span>
                    <span className="cnv-target__price">{priceOf(t.tool)}</span>
                  </label>
                )
              })}
            </div>
          </fieldset>
        )}
        {mode === 'convert' && file && !known && file.ext !== '' && (
          <p className="cnv-muted">
            “.{file.ext}” is not a type this service converts. It handles documents, spreadsheets and data, images, audio and video.
          </p>
        )}

        {mode === 'unpack' && file?.entries && file.entries.length > 0 && (
          <div className="cnv-listing">
            <p className="field__label">Inside this archive</p>
            <ul className="cnv-entries">
              {file.entries.map((e) => (
                <li key={e}>
                  <span className="cnv-entries__name">{e}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {mode === 'pack' && (
          <>
            <div className="cnv-pack">
              {stack.length === 0 ? (
                <p className="cnv-muted">Add the files to put in the archive.</p>
              ) : (
                <ul className="cnv-entries cnv-entries--edit" data-testid="field-file_urls" aria-label="Files to pack">
                  {stack.map((s) => (
                    <li key={s.path}>
                      <span className="cnv-entries__name">{s.name}</span>
                      <button type="button" className="cnv-x" aria-label={`Remove ${s.name}`} onClick={() => setStack((c) => c.filter((x) => x.path !== s.path))}>
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <UploadButton
                testid="cnv-upload"
                label={stack.length ? 'Add another file' : 'Add a file'}
                onPath={(p, f) => setStack((c) => (c.some((x) => x.path === p) ? c : [...c, { path: p, name: f.name, ext: extOf(f.name) }]))}
              />
            </div>
            <fieldset className="cnv-targets">
              <legend className="field__label">Archive format</legend>
              <div className="cnv-targets__grid" data-testid="field-format">
                {ARCHIVE_FORMATS.map((f) => (
                  <label key={f} className={`cnv-target${archiveFmt === f ? ' is-on' : ''}`}>
                    <input type="radio" name={`${uid}-af`} checked={archiveFmt === f} onChange={() => setArchiveFmt(f)} />
                    <span className="cnv-target__ext">{f}</span>
                    <span className="cnv-target__name">{ARCHIVE_NAMES[f]}</span>
                    <span className="cnv-target__price">{priceOf('archive_create')}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </>
        )}

        <div className="cnv-go">
          <PayButton
            label={label}
            running={running}
            runningLabel={mode === 'convert' ? 'Converting. Video can take a minute' : mode === 'pack' ? 'Packing the files' : 'Unpacking'}
            disabled={!ready}
            onClick={go}
          />
          {!ready && !running && (
            <span className="field__hint">
              {mode === 'pack' ? (stack.length ? '' : 'Add a file first.') : !file ? 'Choose a file first.' : mode === 'convert' && !chosen ? 'Pick a format to convert to.' : mode === 'unpack' && !unpackOk ? 'Choose an archive.' : ''}
            </span>
          )}
        </div>
      </section>

      {(running || result) && (
        <section className="cnv-out" aria-label="Result" aria-busy={running}>
          {running && <p className="cnv-muted">Working on it. Payment settles only if the service succeeds.</p>}
          {!running && result?.isError && (
            <p className="cnv-fail">The file could not be converted. The service’s reply is below. Check that the file really is the type its name says.</p>
          )}
          {!running && outPath && sent.current && <Delivered path={outPath} sent={sent.current} />}
          {!running && result && <RawOutput text={text} title="The service’s reply" />}
        </section>
      )}
    </div>
  )
}

export default Convert
