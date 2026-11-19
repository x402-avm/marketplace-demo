import React, { useEffect, useMemo, useRef, useState } from 'react'
import { PayButton, RawOutput, fileName, getFileUrl } from '../kit'
import type { ToolUIProps } from '../kit'
import { DEFAULT_VOICE, describeVoice, voiceGroups } from './voices'
import { TakePlayer } from './TakePlayer'
import './tts.css'

export const domain = 'tts'

const TOOL = 'synthesize_speech'
const LIMIT = 1000
/** Kokoro at normal speed reads about 14 characters a second; replaced by the measured rate once there are takes. */
const DEFAULT_RATE = 14

interface Take {
  n: number
  path: string
  text: string
  voice: string
  duration?: number
}

function spoken(sec: number): string {
  if (sec < 1) return 'under a second'
  if (sec < 60) return `${Math.round(sec)} second${Math.round(sec) === 1 ? '' : 's'}`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec - m * 60)
  return `${m} min ${s} s`
}

const VoiceChoice: React.FC<{ id: string; checked: boolean; disabled: boolean; onPick: (id: string) => void }> = ({ id, checked, disabled, onPick }) => {
  const v = describeVoice(id)
  return (
    <label className={`tts-voice${checked ? ' is-on' : ''}`}>
      <input type="radio" name="tts-voice" value={id} checked={checked} disabled={disabled} onChange={() => onPick(id)} />
      <span className="tts-voice__face">
        <span className="tts-voice__name">{v.name}</span>
        <span className="tts-voice__kind">
          {v.accent !== 'American' && v.accent !== 'British' ? `${v.accent}, ` : ''}
          {v.kind.toLowerCase()}
        </span>
      </span>
    </label>
  )
}

const TtsBooth: React.FC<ToolUIProps> = (props) => {
  const { args, setArgs, running, result, resultTool, text, files, canRun, listing } = props
  const script: string = typeof args.text === 'string' ? args.text : ''
  const voice: string = typeof args.voice === 'string' && args.voice ? args.voice : DEFAULT_VOICE
  const groups = useMemo(voiceGroups, [])
  const current = describeVoice(voice)

  const [takes, setTakes] = useState<Take[]>([])
  const pending = useRef<{ text: string; voice: string } | null>(null)

  // Each successful recording becomes a take; they stay for this visit so they can be compared.
  useEffect(() => {
    if (!result || result.isError || resultTool !== TOOL) return
    const path = files.find((f) => /\.wav$/i.test(f))
    if (!path) return
    setTakes((prev) => {
      if (prev.some((t) => t.path === path)) return prev
      const p = pending.current ?? { text: script, voice }
      return [{ n: prev.length + 1, path, text: p.text, voice: p.voice }, ...prev]
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, resultTool, files])

  const measured = takes.filter((t) => t.duration && t.duration > 0.5)
  const rate = measured.length
    ? measured.reduce((a, t) => a + t.text.length, 0) / measured.reduce((a, t) => a + (t.duration ?? 0), 0)
    : DEFAULT_RATE
  const count = script.length
  const over = count - LIMIT
  const blank = script.trim().length === 0
  const fill = Math.min(1, count / LIMIT)

  const usesPass = props.payLabel.startsWith('Run with')
  const label = usesPass ? 'Record with your pass' : `Pay ${props.priceOf(TOOL)} and record`

  const record = () => {
    pending.current = { text: script, voice }
    props.run({ tool: TOOL, args: { text: script, voice } })
  }

  const setVoice = (id: string) => setArgs({ ...args, text: script, voice: id })

  const errorText = result?.isError && resultTool === TOOL ? text : ''

  return (
    <div className="tts">
      <div className="tts-desk">
        <section className="tts-script" aria-labelledby="tts-script-label">
          <label id="tts-script-label" htmlFor="tts-text" className="tts-h">
            Script
          </label>
          <p className="tts-hint" id="tts-text-hint">
            Write what you want said. Punctuation sets the pauses.
          </p>
          <textarea
            id="tts-text"
            className="tts-text"
            data-testid="field-text"
            value={script}
            placeholder="Thanks for calling. Your order shipped this morning and should arrive on Thursday."
            aria-describedby="tts-text-hint tts-meter"
            aria-invalid={over > 0}
            spellCheck
            disabled={running}
            onChange={(e) => setArgs({ ...args, voice, text: e.target.value })}
          />
          <div className={`tts-meter${over > 0 ? ' is-over' : ''}`} id="tts-meter">
            <div className="tts-meter__track" aria-hidden="true">
              <span className="tts-meter__fill" style={{ width: `${fill * 100}%` }} />
            </div>
            <p className="tts-meter__count">
              {over > 0 ? (
                <>
                  <strong>{over}</strong> characters over the {LIMIT} limit. Shorten the script or split it into two takes.
                </>
              ) : (
                <>
                  <strong>{count}</strong> of {LIMIT} characters
                </>
              )}
            </p>
            <p className="tts-meter__time">{blank ? 'Nothing to read yet' : `About ${spoken(count / rate)} spoken`}</p>
          </div>
          <div className="tts-go">
            <p className="tts-go__who">
              Read by <strong>{current.name}</strong>, {current.accent === 'American' || current.accent === 'British' ? `${current.accent} English` : `${current.accent} accent`}
            </p>
            <PayButton
              label={label}
              running={running}
              runningLabel={`Recording with ${current.name}`}
              disabled={!canRun || blank || over > 0 || listing.online === false}
              onClick={record}
            />
          </div>
        </section>

        <fieldset className="tts-cast" data-testid="field-voice" data-value={voice} disabled={running}>
          <legend className="tts-h">Voice</legend>
          {groups.slice(0, 2).map((g) => (
            <div className="tts-cast__group" key={g.title}>
              <p className="tts-cast__title">{g.title}</p>
              <div className="tts-cast__list">
                {g.voices.map((v) => (
                  <VoiceChoice key={v.id} id={v.id} checked={v.id === voice} disabled={running} onPick={setVoice} />
                ))}
              </div>
            </div>
          ))}
          <details className="tts-cast__more" open={groups[2].voices.some((v) => v.id === voice) || undefined}>
            <summary>{groups[2].voices.length} voices with other accents</summary>
            <p className="tts-hint">{groups[2].note}</p>
            <div className="tts-cast__list">
              {groups[2].voices.map((v) => (
                <VoiceChoice key={v.id} id={v.id} checked={v.id === voice} disabled={running} onPick={setVoice} />
              ))}
            </div>
          </details>
        </fieldset>
      </div>

      <section className="tts-takes" aria-labelledby="tts-takes-title" aria-busy={running}>
        <div className="tts-takes__head">
          <h2 id="tts-takes-title" className="tts-h">
            Takes
          </h2>
          {takes.length > 1 && <p className="tts-hint">Play them one after another to compare. Only one plays at a time.</p>}
        </div>

        {running && (
          <div className="tts-take tts-take--pending" role="status">
            <span className="tts-take__n">Take {takes.length + 1}</span>
            <p className="tts-take__line">
              {current.name} is reading {count} characters. The take appears here when the recording is ready.
            </p>
            <div className="tts-take__pulse" aria-hidden="true" />
          </div>
        )}

        {!running && errorText && (
          <div className="tts-fail" role="alert">
            <p className="tts-fail__what">The voice service could not record this script.</p>
            <p className="tts-fail__why">{errorText.replace(/^Error:\s*/, '')}</p>
          </div>
        )}

        {takes.length === 0 && !running && !errorText && (
          <p className="tts-empty">No takes yet. Write a script, pick a voice and record. Every take from this visit stays here so you can compare voices.</p>
        )}

        {takes.length > 0 && (
          <ol className="tts-takes__list" reversed>
            {takes.map((t, i) => {
              const v = describeVoice(t.voice)
              return (
                <li key={t.path} className={`tts-take${i === 0 ? ' is-latest' : ''}`}>
                  <div className="tts-take__meta">
                    <span className="tts-take__n">Take {t.n}</span>
                    <span className="tts-take__voice">{v.name}</span>
                  </div>
                  <p className="tts-take__line" title={t.text}>
                    {t.text}
                  </p>
                  <TakePlayer
                    url={getFileUrl(t.path)}
                    fileName={fileName(t.path)}
                    label={`take ${t.n} by ${v.name}`}
                    large={i === 0}
                    onDuration={(d) => setTakes((prev) => prev.map((x) => (x.path === t.path ? { ...x, duration: d } : x)))}
                  />
                </li>
              )
            })}
          </ol>
        )}

        {result && <RawOutput text={text} title="What the service said" />}
      </section>
    </div>
  )
}

export default TtsBooth
