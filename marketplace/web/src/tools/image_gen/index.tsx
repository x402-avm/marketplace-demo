import React, { useEffect, useRef, useState } from 'react'
import { PayButton, RawOutput, UploadButton, getFileUrl, fileName, parseJson } from '../kit'
import type { ToolUIProps } from '../kit'
import './image_gen.css'

export const domain = 'image_gen'

/* Real option values from the image runtime (app/agents/prompt_optimizer.py, app/config.py, app/api/routes.py). */
const STYLES: { id: string; name: string; look: string }[] = [
  { id: 'photorealistic', name: 'Photograph', look: 'Natural light, true textures, a 35mm lens' },
  { id: 'cinematic_8k', name: 'Film still', look: 'Widescreen framing, volumetric light, graded colour' },
  { id: 'studio_portrait', name: 'Studio portrait', look: 'Rembrandt lighting, shallow focus, clean backdrop' },
  { id: 'analog_film', name: 'Analog film', look: 'Film grain, soft highlights, natural colour' },
  { id: 'anime_manga', name: 'Anime', look: 'Cel shading, crisp linework, sky gradients' },
  { id: 'fantasy_oil', name: 'Oil painting', look: 'Visible brushwork, rich contrast, chiaroscuro' },
  { id: 'cyberpunk', name: 'Cyberpunk', look: 'Neon signs, wet streets, dusk' },
  { id: 'minimalist_vector', name: 'Flat graphic', look: 'Geometric shapes, negative space, few colours' },
]

const ASPECTS: { id: string; name: string; w: number; h: number }[] = [
  { id: '1:1', name: 'Square', w: 512, h: 512 },
  { id: '4:3', name: 'Classic', w: 640, h: 480 },
  { id: '3:2', name: 'Photo', w: 600, h: 400 },
  { id: '16:9', name: 'Wide', w: 768, h: 432 },
  { id: '9:16', name: 'Tall', w: 432, h: 768 },
]

const FILTERS: { id: string; name: string }[] = [
  { id: 'none', name: 'No look' },
  { id: 'auto_enhance', name: 'Auto enhance' },
  { id: 'cinematic', name: 'Cinematic' },
  { id: 'hdr', name: 'HDR' },
  { id: 'noir', name: 'Noir' },
  { id: 'portrait_bokeh', name: 'Soft background' },
  { id: 'warm_golden', name: 'Warm golden' },
  { id: 'cool_neon', name: 'Cool neon' },
  { id: 'vintage', name: 'Vintage' },
  { id: 'pencil_sketch', name: 'Pencil sketch' },
  { id: 'edge_detect', name: 'Outlines only' },
]

interface Shot {
  id: number
  kind: 'generate' | 'edit'
  path: string
  prompt: string
  style?: string
  aspect?: string
  seed?: number
  steps?: number
  backend?: string
  latency?: number
  grade?: string
  score?: number
  from?: string
  filter?: string
}

type Pending = { tool: string; args: Record<string, any>; extra?: Partial<Shot> }

const SHOTS_KEY = 'image_gen.shots'
const randomSeed = () => Math.floor(Math.random() * 2_000_000_000)
const engineName = (b?: string) => (b ? b.replace(/^diffusers:/, '').replace(/^[^/]+\//, '') : 'unknown')
const styleName = (id?: string) => STYLES.find((s) => s.id === id)?.name ?? id ?? ''

function loadShots(): Shot[] {
  try {
    const raw = sessionStorage.getItem(SHOTS_KEY)
    return raw ? (JSON.parse(raw) as Shot[]) : []
  } catch {
    return []
  }
}

const ImageStudio: React.FC<ToolUIProps> = ({ run, running, result, resultTool, text, priceOf, payLabel, canRun, listing }) => {
  const [mode, setMode] = useState<'generate' | 'edit'>('generate')

  // new image
  const [prompt, setPrompt] = useState('')
  const [style, setStyle] = useState('photorealistic')
  const [aspect, setAspect] = useState('1:1')
  const [steps, setSteps] = useState(15)
  const [guidance, setGuidance] = useState(7.5)
  const [seed, setSeed] = useState<number>(() => randomSeed())
  const [keepSeed, setKeepSeed] = useState(false)
  const [negative, setNegative] = useState('')
  const [autoOpt, setAutoOpt] = useState(true)

  // change an image
  const [source, setSource] = useState<{ path: string; url: string; name: string } | null>(null)
  const [sourcePath, setSourcePath] = useState('')
  const [editPrompt, setEditPrompt] = useState('')
  const [filter, setFilter] = useState('auto_enhance')
  const [strength, setStrength] = useState(0.65)
  const [brightness, setBrightness] = useState(1)
  const [contrast, setContrast] = useState(1)
  const [sharpness, setSharpness] = useState(1)
  const [editSteps, setEditSteps] = useState(15)

  // what came back
  const [shots, setShots] = useState<Shot[]>(loadShots)
  const [current, setCurrent] = useState<number | null>(() => {
    const s = loadShots()
    return s.length ? s[s.length - 1].id : null
  })
  const [optimized, setOptimized] = useState<any>(null)
  const [promptApplied, setPromptApplied] = useState(false)
  const [quality, setQuality] = useState<{ path: string; r: any } | null>(null)
  const [hardware, setHardware] = useState<any>(null)
  const [failure, setFailure] = useState<{ tool: string; text: string } | null>(null)
  const [elapsed, setElapsed] = useState(0)

  const pending = useRef<Pending | null>(null)
  const seen = useRef<unknown>(null)
  const canvasRef = useRef<HTMLDivElement>(null)

  const usePass = payLabel.startsWith('Run with')
  const pay = (tool: string) => (usePass ? 'with your pass' : priceOf(tool))
  const shot = shots.find((s) => s.id === current) ?? null
  const runningTool = running ? pending.current?.tool ?? null : null
  const drawing = runningTool === 'generate_image' || runningTool === 'edit_image'

  useEffect(() => {
    try {
      sessionStorage.setItem(SHOTS_KEY, JSON.stringify(shots.slice(-24)))
    } catch {
      /* storage may be unavailable; the strip still works for this page view */
    }
  }, [shots])

  useEffect(() => {
    if (!drawing) return
    setElapsed(0)
    const t0 = Date.now()
    const id = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 1000)
    return () => clearInterval(id)
  }, [drawing])

  // File each result where it belongs.
  useEffect(() => {
    if (!result || result === seen.current) return
    seen.current = result
    const job = pending.current
    const tool = resultTool ?? job?.tool ?? ''
    if (result.isError) {
      setFailure({ tool, text })
      return
    }
    setFailure(null)
    const r = parseJson<any>(text)
    if (tool === 'generate_image' || tool === 'edit_image') {
      if (!r?.file_path) {
        setFailure({ tool, text: text || 'No image path came back.' })
        return
      }
      const id = Date.now()
      const isGen = tool === 'generate_image'
      const s: Shot = {
        id,
        kind: isGen ? 'generate' : 'edit',
        path: r.file_path,
        prompt: (isGen ? job?.args.prompt : job?.args.prompt) || '',
        backend: r.backend,
        latency: isGen ? r.latency_seconds : r.total_latency_seconds,
        grade: isGen ? r.grade : r.qa_report?.grade,
        score: isGen ? r.quality_score : r.qa_report?.quality_score,
        ...job?.extra,
      }
      setShots((prev) => [...prev, s])
      setCurrent(id)
      if (typeof window !== 'undefined' && window.innerWidth < 900) {
        const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
        requestAnimationFrame(() => canvasRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }))
      }
    } else if (tool === 'optimize_prompt') {
      setOptimized(r)
      setPromptApplied(false)
    } else if (tool === 'analyze_image_quality') {
      setQuality({ path: job?.args.image_path ?? '', r })
    } else if (tool === 'get_hardware_status') {
      setHardware(r)
    }
  }, [result, resultTool, text])

  const call = (tool: string, args: Record<string, any>, extra?: Partial<Shot>) => {
    pending.current = { tool, args, extra }
    setFailure(null)
    run({ tool, args })
  }

  const generate = () => {
    const useSeed = keepSeed ? seed : randomSeed()
    setSeed(useSeed)
    const args = {
      prompt: prompt.trim(),
      style,
      negative_prompt: negative.trim(),
      aspect_ratio: aspect,
      steps,
      guidance_scale: guidance,
      seed: useSeed,
      auto_optimize: autoOpt,
    }
    call('generate_image', args, { style, aspect, seed: useSeed, steps })
  }

  const applyEdit = () => {
    if (!source) return
    const args: Record<string, any> = {
      image_path: source.path,
      prompt: editPrompt.trim(),
      filter_preset: filter,
      brightness,
      contrast,
      sharpness,
      strength,
      steps: editSteps,
    }
    call('edit_image', args, { from: source.path, filter, steps: editSteps })
  }

  const editThis = (s: Shot) => {
    setSource({ path: s.path, url: getFileUrl(s.path), name: fileName(s.path) })
    setSourcePath(s.path)
    setMode('edit')
  }

  const reuseSeed = (s: Shot) => {
    if (s.seed === undefined) return
    setSeed(s.seed)
    setKeepSeed(true)
    if (s.prompt) setPrompt(s.prompt)
    if (s.style) setStyle(s.style)
    if (s.aspect) setAspect(s.aspect)
    setMode('generate')
  }

  const aspectInfo = ASPECTS.find((a) => a.id === aspect) ?? ASPECTS[0]
  const genFailed = failure && (failure.tool === 'generate_image' || failure.tool === 'edit_image')
  const helperFailed = failure && !genFailed ? failure : null

  return (
    <div className="imggen">
      {/* ------------------------------------------------ controls */}
      <div className="imggen__controls">
        <div className="imggen__modes" role="radiogroup" aria-label="What to do">
          <button
            type="button"
            role="radio"
            aria-checked={mode === 'generate'}
            className={`imggen__mode${mode === 'generate' ? ' is-on' : ''}`}
            data-testid="mode-generate"
            onClick={() => setMode('generate')}
          >
            New image
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={mode === 'edit'}
            className={`imggen__mode${mode === 'edit' ? ' is-on' : ''}`}
            data-testid="mode-edit"
            onClick={() => setMode('edit')}
          >
            Change an image
          </button>
        </div>

        {mode === 'generate' ? (
          <div className="imggen__form">
            <div className="imggen__field">
              <label htmlFor="imggen-prompt" className="imggen__label">
                Describe the picture
              </label>
              <textarea
                id="imggen-prompt"
                className="input imggen__prompt"
                data-testid="field-prompt"
                rows={4}
                value={prompt}
                placeholder="A red fox curled up asleep in fresh snow, early morning"
                onChange={(e) => setPrompt(e.target.value)}
              />
            </div>

            <fieldset className="imggen__field" data-testid="field-style">
              <legend className="imggen__label">Style</legend>
              <div className="imggen__styles">
                {STYLES.map((s) => (
                  <label key={s.id} className={`imggen__chip${style === s.id ? ' is-on' : ''}`}>
                    <input type="radio" name="imggen-style" value={s.id} checked={style === s.id} onChange={() => setStyle(s.id)} />
                    {s.name}
                  </label>
                ))}
              </div>
              <p className="imggen__hint">{STYLES.find((s) => s.id === style)?.look}</p>
            </fieldset>

            <fieldset className="imggen__field" data-testid="field-aspect_ratio">
              <legend className="imggen__label">Shape</legend>
              <div className="imggen__aspects">
                {ASPECTS.map((a) => {
                  const k = 34 / Math.max(a.w, a.h)
                  return (
                    <label key={a.id} className={`imggen__aspect${aspect === a.id ? ' is-on' : ''}`} title={`${a.w} by ${a.h} pixels`}>
                      <input type="radio" name="imggen-aspect" value={a.id} checked={aspect === a.id} onChange={() => setAspect(a.id)} />
                      <span className="imggen__frame" style={{ width: Math.round(a.w * k), height: Math.round(a.h * k) }} aria-hidden="true" />
                      <span className="imggen__aspectname">{a.name}</span>
                      <span className="imggen__aspectratio">{a.id}</span>
                    </label>
                  )
                })}
              </div>
            </fieldset>

            <Slider
              id="imggen-steps"
              testid="field-steps"
              label="Detail passes"
              value={steps}
              min={1}
              max={50}
              step={1}
              onChange={setSteps}
              show={(v) => `${v} steps`}
              ends={['Faster', 'More refined']}
            />
            <Slider
              id="imggen-guidance"
              testid="field-guidance_scale"
              label="How closely to follow the words"
              value={guidance}
              min={1}
              max={20}
              step={0.5}
              onChange={setGuidance}
              show={(v) => v.toFixed(1)}
              ends={['Loose', 'Literal']}
            />

            <div className="imggen__field">
              <label htmlFor="imggen-seed" className="imggen__label">
                Seed
              </label>
              <div className="imggen__seedrow">
                <input
                  id="imggen-seed"
                  className="input imggen__seed"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  data-testid="field-seed"
                  value={seed}
                  onChange={(e) => setSeed(Math.max(0, Math.floor(Number(e.target.value) || 0)))}
                />
                <button type="button" className="imggen__btn" onClick={() => setSeed(randomSeed())}>
                  New seed
                </button>
              </div>
              <label className="imggen__check">
                <input type="checkbox" checked={keepSeed} data-testid="keep-seed" onChange={(e) => setKeepSeed(e.target.checked)} />
                Keep this seed
              </label>
              <p className="imggen__hint">
                {keepSeed
                  ? 'The same seed with the same words draws the same picture, so you can change one setting at a time.'
                  : 'A fresh seed is picked for every image. Tick the box to hold on to one you like.'}
              </p>
            </div>

            <details className="imggen__more">
              <summary>Leave things out, and prompt expansion</summary>
              <div className="imggen__field">
                <label htmlFor="imggen-neg" className="imggen__label">
                  Leave out
                </label>
                <textarea
                  id="imggen-neg"
                  className="input"
                  rows={2}
                  data-testid="field-negative_prompt"
                  value={negative}
                  placeholder="blurry, text, extra fingers"
                  onChange={(e) => setNegative(e.target.value)}
                />
              </div>
              <label className="imggen__check">
                <input type="checkbox" data-testid="field-auto_optimize" checked={autoOpt} onChange={(e) => setAutoOpt(e.target.checked)} />
                Expand my description with style details before drawing
              </label>
            </details>

            <PayButton
              label={`Generate image, ${pay('generate_image')}`}
              running={running}
              runningLabel={drawing ? `Drawing, ${elapsed} s` : 'Waiting for the service'}
              disabled={!canRun || !prompt.trim() || listing.online === false}
              onClick={generate}
            />
            {!prompt.trim() && <p className="imggen__hint">Describe the picture first.</p>}
          </div>
        ) : (
          <div className="imggen__form">
            <div className="imggen__field">
              <span className="imggen__label">Image to change</span>
              {source ? (
                <div className="imggen__source">
                  <img src={source.url} alt="The image that will be changed" />
                  <span className="imggen__sourcename">{source.name}</span>
                </div>
              ) : (
                <p className="imggen__hint">Pick one you made below the canvas, or upload your own.</p>
              )}
              <div className="imggen__sourcebtns">
                {shot && shot.path !== source?.path && (
                  <button type="button" className="imggen__btn" onClick={() => editThis(shot)}>
                    Use the image on the canvas
                  </button>
                )}
                <UploadButton
                  accept="image/png,image/jpeg,image/webp"
                  label="Upload an image"
                  testid="upload-source"
                  onPath={(path, file) => {
                    setSource({ path, url: URL.createObjectURL(file), name: file.name })
                    setSourcePath(path)
                  }}
                />
              </div>
              <details className="imggen__more">
                <summary>Use a file already on the server</summary>
                <div className="imggen__seedrow">
                  <label htmlFor="imggen-path" className="visually-hidden">
                    Server path of the image
                  </label>
                  <input
                    id="imggen-path"
                    className="input"
                    data-testid="field-image_path"
                    value={sourcePath}
                    placeholder="/path/to/image.png"
                    onChange={(e) => setSourcePath(e.target.value)}
                  />
                  <button
                    type="button"
                    className="imggen__btn"
                    disabled={!sourcePath.trim()}
                    onClick={() => setSource({ path: sourcePath.trim(), url: getFileUrl(sourcePath.trim()), name: fileName(sourcePath.trim()) })}
                  >
                    Use it
                  </button>
                </div>
              </details>
            </div>

            <div className="imggen__field">
              <label htmlFor="imggen-editprompt" className="imggen__label">
                Describe the change <span className="imggen__opt">(optional)</span>
              </label>
              <textarea
                id="imggen-editprompt"
                className="input imggen__prompt"
                data-testid="field-prompt"
                rows={3}
                value={editPrompt}
                placeholder="Make it night time, with a full moon"
                onChange={(e) => setEditPrompt(e.target.value)}
              />
              <p className="imggen__hint">
                {editPrompt.trim()
                  ? 'The model repaints the picture following your words, then applies the look and adjustments.'
                  : 'With no description, only the look and the adjustments below are applied. Nothing is repainted.'}
              </p>
            </div>

            <fieldset className="imggen__field" data-testid="field-filter_preset">
              <legend className="imggen__label">Look</legend>
              <div className="imggen__styles">
                {FILTERS.map((f) => (
                  <label key={f.id} className={`imggen__chip${filter === f.id ? ' is-on' : ''}`}>
                    <input type="radio" name="imggen-filter" value={f.id} checked={filter === f.id} onChange={() => setFilter(f.id)} />
                    {f.name}
                  </label>
                ))}
              </div>
            </fieldset>

            {editPrompt.trim() && (
              <>
                <Slider
                  id="imggen-strength"
                  testid="field-strength"
                  label="How much may change"
                  value={strength}
                  min={0.1}
                  max={1}
                  step={0.05}
                  onChange={setStrength}
                  show={(v) => `${Math.round(v * 100)}%`}
                  ends={['Keep the original', 'Repaint freely']}
                />
                <Slider id="imggen-editsteps" testid="field-steps" label="Detail passes" value={editSteps} min={1} max={50} step={1} onChange={setEditSteps} show={(v) => `${v} steps`} />
              </>
            )}
            <div className="imggen__adjust">
              <Slider id="imggen-bright" testid="field-brightness" label="Brightness" value={brightness} min={0.5} max={2} step={0.05} onChange={setBrightness} show={(v) => `${Math.round(v * 100)}%`} />
              <Slider id="imggen-contrast" testid="field-contrast" label="Contrast" value={contrast} min={0.5} max={2} step={0.05} onChange={setContrast} show={(v) => `${Math.round(v * 100)}%`} />
              <Slider id="imggen-sharp" testid="field-sharpness" label="Sharpness" value={sharpness} min={0.5} max={2} step={0.05} onChange={setSharpness} show={(v) => `${Math.round(v * 100)}%`} />
            </div>

            <PayButton
              label={`Apply the change, ${pay('edit_image')}`}
              running={running}
              runningLabel={drawing ? `Changing the image, ${elapsed} s` : 'Waiting for the service'}
              disabled={!canRun || !source || listing.online === false}
              onClick={applyEdit}
            />
            {!source && <p className="imggen__hint">Choose the image to change first.</p>}
          </div>
        )}
      </div>

      {/* ------------------------------------------------ canvas */}
      <div className="imggen__stage" ref={canvasRef}>
        <div
          className={`imggen__canvas${drawing ? ' is-drawing' : ''}`}
          style={!shot || drawing ? { aspectRatio: mode === 'generate' ? `${aspectInfo.w} / ${aspectInfo.h}` : '4 / 3' } : undefined}
          aria-live="polite"
        >
          {drawing ? (
            <p className="imggen__wait">
              {runningTool === 'generate_image' ? 'Drawing your image' : 'Changing your image'}
              <span className="imggen__waitsub">
                {elapsed} s so far. It usually takes 5 to 30 seconds. You pay only if an image comes back.
              </span>
            </p>
          ) : shot ? (
            <img key={shot.path} src={getFileUrl(shot.path)} alt={shot.prompt ? `Generated: ${shot.prompt}` : 'Generated image'} className="imggen__img" data-testid="imggen-image" />
          ) : (
            <p className="imggen__wait">
              {mode === 'generate' ? `Your ${aspectInfo.name.toLowerCase()} image, ${aspectInfo.w} by ${aspectInfo.h} pixels, appears here.` : 'The changed image appears here.'}
            </p>
          )}
        </div>

        {genFailed && !running && (
          <p className="imggen__error" role="alert">
            {failure!.tool === 'generate_image' ? 'The image was not generated.' : 'The image was not changed.'} The service said: {failure!.text || 'nothing'}
          </p>
        )}

        {shot && !drawing && <ShotDetails shot={shot} onEdit={() => editThis(shot)} onSeed={() => reuseSeed(shot)} />}

        {shots.length > 0 && (
          <div className="imggen__strip">
            <p className="imggen__striptitle">
              Made this visit <span className="imggen__count">{shots.length}</span>
            </p>
            <ul className="imggen__thumbs">
              {[...shots].reverse().map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className={`imggen__thumb${s.id === current ? ' is-on' : ''}`}
                    aria-pressed={s.id === current}
                    aria-label={`${s.kind === 'edit' ? 'Changed image' : 'Image'}: ${s.prompt || styleName(s.filter)}`}
                    onClick={() => setCurrent(s.id)}
                  >
                    <img src={getFileUrl(s.path)} alt="" loading="lazy" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {result && !running && <RawOutput text={text} title="What the service sent back last" />}
      </div>

      {/* ------------------------------------------------ helpers */}
      <aside className="imggen__helpers" aria-labelledby="imggen-helpers-h">
        <h2 id="imggen-helpers-h" className="svc__h2 imggen__h">
          Helpers
        </h2>
        <div className="imggen__helperbtns">
          <HelperButton
            title="Improve my prompt"
            note="Rewrites your description for the chosen style."
            price={pay('optimize_prompt')}
            busy={runningTool === 'optimize_prompt'}
            disabled={!canRun || running || !prompt.trim()}
            testid="helper-optimize"
            onClick={() => call('optimize_prompt', { prompt: prompt.trim(), style })}
          />
          <HelperButton
            title="Grade the image"
            note="Sharpness, contrast, exposure and what to fix."
            price={pay('analyze_image_quality')}
            busy={runningTool === 'analyze_image_quality'}
            disabled={!canRun || running || !(shot || source)}
            testid="helper-quality"
            onClick={() => call('analyze_image_quality', { image_path: (shot ?? source)!.path })}
          />
          <HelperButton
            title="Check the machine"
            note="Which processor draws, and how much memory is free."
            price={pay('get_hardware_status')}
            busy={runningTool === 'get_hardware_status'}
            disabled={!canRun || running}
            testid="helper-hardware"
            onClick={() => call('get_hardware_status', {})}
          />
        </div>

        {helperFailed && !running && (
          <p className="imggen__error" role="alert">
            That helper did not finish. The service said: {helperFailed.text || 'nothing'}
          </p>
        )}

        <div className="imggen__notes" aria-live="polite">
          {optimized?.optimized_prompt && (
            <section className="imggen__note" aria-label="Improved prompt">
              <h3 className="imggen__noteh">Improved prompt</h3>
              <p className="imggen__suggest">{optimized.optimized_prompt}</p>
              {optimized.negative_prompt && <p className="imggen__hint">Leaves out: {optimized.negative_prompt}</p>}
              {promptApplied ? (
                <p className="imggen__hint" role="status">
                  Your description now uses this prompt. Automatic expansion is off, since it is already expanded.
                </p>
              ) : (
                <button
                  type="button"
                  className="imggen__btn imggen__btn--strong"
                  data-testid="use-optimized"
                  onClick={() => {
                    setPrompt(optimized.optimized_prompt)
                    if (optimized.negative_prompt) setNegative(optimized.negative_prompt)
                    setAutoOpt(false)
                    setPromptApplied(true)
                    setMode('generate')
                  }}
                >
                  Replace my prompt with this
                </button>
              )}
            </section>
          )}

          {quality?.r && <QualityNote q={quality.r} path={quality.path} />}

          {hardware && (
            <section className="imggen__note" aria-label="Machine status">
              <h3 className="imggen__noteh">The machine</h3>
              <dl className="imggen__facts">
                <div>
                  <dt>Processor</dt>
                  <dd>{hardware.cpu_model ?? 'unknown'}</dd>
                </div>
                {hardware.dgpu_description && (
                  <div>
                    <dt>Graphics card</dt>
                    <dd>{hardware.dgpu_description}</dd>
                  </div>
                )}
                <div>
                  <dt>Helpers run on</dt>
                  <dd>{hardware.device === 'cpu' ? 'The processor' : hardware.device}</dd>
                </div>
                {typeof hardware.memory_used_percent === 'number' && (
                  <div>
                    <dt>Memory in use</dt>
                    <dd>
                      <Meter value={hardware.memory_used_percent} label={`${Math.round(hardware.memory_used_percent)}% of ${hardware.memory_total_gb} GB`} />
                    </dd>
                  </div>
                )}
              </dl>
            </section>
          )}
          {!optimized && !quality && !hardware && !helperFailed && (
            <p className="imggen__hint">Each helper is a small paid call. Its answer shows here and nothing on the canvas changes.</p>
          )}
        </div>
      </aside>
    </div>
  )
}

/* ------------------------------------------------ pieces */

const Slider: React.FC<{
  id: string
  testid: string
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (v: number) => void
  show: (v: number) => string
  ends?: [string, string]
}> = ({ id, testid, label, value, min, max, step, onChange, show, ends }) => (
  <div className="imggen__field imggen__slider">
    <div className="imggen__sliderhead">
      <label htmlFor={id} className="imggen__label">
        {label}
      </label>
      <output htmlFor={id} className="imggen__val">
        {show(value)}
      </output>
    </div>
    <input id={id} className="imggen__range" type="range" min={min} max={max} step={step} value={value} data-testid={testid} onChange={(e) => onChange(Number(e.target.value))} />
    {ends && (
      <div className="imggen__ends" aria-hidden="true">
        <span>{ends[0]}</span>
        <span>{ends[1]}</span>
      </div>
    )}
  </div>
)

const HelperButton: React.FC<{ title: string; note: string; price: string; busy: boolean; disabled: boolean; testid: string; onClick: () => void }> = ({
  title,
  note,
  price,
  busy,
  disabled,
  testid,
  onClick,
}) => (
  <button type="button" className="imggen__helper" data-testid={testid} disabled={disabled} onClick={onClick}>
    <span className="imggen__helpertitle">{busy ? `${title}: working` : title}</span>
    <span className="imggen__helperprice">{price}</span>
    <span className="imggen__helpernote">{note}</span>
  </button>
)

const Meter: React.FC<{ value: number; label: string }> = ({ value, label }) => (
  <span className="imggen__meter">
    <span className="imggen__bar" aria-hidden="true">
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </span>
    <span>{label}</span>
  </span>
)

const ShotDetails: React.FC<{ shot: Shot; onEdit: () => void; onSeed: () => void }> = ({ shot, onEdit, onSeed }) => {
  const [dims, setDims] = useState<string | null>(null)
  useEffect(() => {
    setDims(null)
    const img = new Image()
    img.onload = () => setDims(`${img.naturalWidth} by ${img.naturalHeight}`)
    img.src = getFileUrl(shot.path)
  }, [shot.path])
  return (
    <div className="imggen__details">
      {shot.prompt ? (
        <p className="imggen__caption">{shot.prompt}</p>
      ) : (
        <p className="imggen__caption imggen__caption--quiet">{shot.kind === 'edit' ? `Look applied: ${FILTERS.find((f) => f.id === shot.filter)?.name ?? shot.filter}` : 'Untitled'}</p>
      )}
      <dl className="imggen__meta" data-testid="imggen-meta">
        {shot.grade && (
          <div className="imggen__grade">
            <dt>Quality</dt>
            <dd>
              <span className="imggen__gradeletter">{shot.grade}</span>
              {typeof shot.score === 'number' && <span className="imggen__score">{shot.score.toFixed(1)} of 100</span>}
            </dd>
          </div>
        )}
        {typeof shot.latency === 'number' && (
          <div>
            <dt>Took</dt>
            <dd>{shot.latency.toFixed(1)} s</dd>
          </div>
        )}
        <div>
          <dt>Model</dt>
          <dd>{engineName(shot.backend)}</dd>
        </div>
        {dims && (
          <div>
            <dt>Size</dt>
            <dd>{dims}</dd>
          </div>
        )}
        {shot.style && (
          <div>
            <dt>Style</dt>
            <dd>{styleName(shot.style)}</dd>
          </div>
        )}
        {shot.seed !== undefined && (
          <div>
            <dt>Seed</dt>
            <dd>{shot.seed}</dd>
          </div>
        )}
      </dl>
      <div className="imggen__actions">
        {shot.seed !== undefined && (
          <button type="button" className="imggen__btn" onClick={onSeed} data-testid="reuse-seed">
            Keep this seed and settings
          </button>
        )}
        <button type="button" className="imggen__btn" onClick={onEdit}>
          Change this image
        </button>
        <a className="imggen__link" href={getFileUrl(shot.path)} target="_blank" rel="noopener noreferrer">
          Open full size
        </a>
      </div>
    </div>
  )
}

const METRICS: [string, string][] = [
  ['sharpness', 'Sharpness'],
  ['contrast', 'Contrast'],
  ['exposure', 'Exposure'],
  ['vibrancy', 'Colour'],
]

const QualityNote: React.FC<{ q: any; path: string }> = ({ q, path }) => (
  <section className="imggen__note" aria-label="Image grade">
    <h3 className="imggen__noteh">Grade for {fileName(path)}</h3>
    <p className="imggen__gradeline">
      <span className="imggen__gradeletter">{q.grade ?? '?'}</span>
      <span>
        {typeof q.quality_score === 'number' ? `${q.quality_score.toFixed(1)} of 100` : ''}
        {q.status ? `. ${q.status}` : ''}
      </span>
    </p>
    {q.metrics && (
      <dl className="imggen__facts">
        {METRICS.filter(([k]) => typeof q.metrics[k] === 'number').map(([k, name]) => (
          <div key={k}>
            <dt>{name}</dt>
            <dd>
              <Meter value={q.metrics[k]} label={`${Math.round(q.metrics[k])}`} />
            </dd>
          </div>
        ))}
        {q.metrics.resolution && (
          <div>
            <dt>Size</dt>
            <dd>{String(q.metrics.resolution).replace('x', ' by ')}</dd>
          </div>
        )}
      </dl>
    )}
    {Array.isArray(q.suggestions) && q.suggestions.length > 0 && (
      <ul className="imggen__tips">
        {q.suggestions.map((s: string, i: number) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    )}
  </section>
)

export default ImageStudio
