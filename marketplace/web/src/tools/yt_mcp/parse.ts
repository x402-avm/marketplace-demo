/** The YouTube service answers with a Python dict printed as text ({'status': 'success', ...}). Read it, or JSON. */
export function readPyLiteral(src: string): any {
  let i = 0
  const s = src.trim()
  const ws = () => {
    while (i < s.length && /\s/.test(s[i])) i++
  }
  const fail = (): never => {
    throw new Error(`Unexpected input at ${i}`)
  }
  const str = (): string => {
    const q = s[i++]
    let out = ''
    while (i < s.length && s[i] !== q) {
      if (s[i] === '\\') {
        const c = s[i + 1]
        i += 2
        if (c === 'n') out += '\n'
        else if (c === 't') out += '\t'
        else if (c === 'r') out += '\r'
        else if (c === 'x') {
          out += String.fromCharCode(parseInt(s.slice(i, i + 2), 16))
          i += 2
        } else if (c === 'u') {
          out += String.fromCharCode(parseInt(s.slice(i, i + 4), 16))
          i += 4
        } else out += c
      } else out += s[i++]
    }
    if (s[i] !== q) fail()
    i++
    return out
  }
  const value = (): any => {
    ws()
    const c = s[i]
    if (c === '{') {
      i++
      const o: Record<string, any> = {}
      ws()
      if (s[i] === '}') return i++, o
      for (;;) {
        const k = value()
        ws()
        if (s[i++] !== ':') fail()
        o[String(k)] = value()
        ws()
        if (s[i] === ',') {
          i++
          ws()
          if (s[i] === '}') return i++, o
          continue
        }
        if (s[i++] !== '}') fail()
        return o
      }
    }
    if (c === '[' || c === '(') {
      const close = c === '[' ? ']' : ')'
      i++
      const a: any[] = []
      ws()
      if (s[i] === close) return i++, a
      for (;;) {
        a.push(value())
        ws()
        if (s[i] === ',') {
          i++
          ws()
          if (s[i] === close) return i++, a
          continue
        }
        if (s[i++] !== close) fail()
        return a
      }
    }
    if (c === "'" || c === '"') return str()
    const m = /^(True|False|None|true|false|null|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)/.exec(s.slice(i))
    if (!m) fail()
    i += m![0].length
    const t = m![0]
    if (t === 'True' || t === 'true') return true
    if (t === 'False' || t === 'false') return false
    if (t === 'None' || t === 'null') return null
    return Number(t)
  }
  const v = value()
  ws()
  if (i !== s.length) fail()
  return v
}

export function readResult(text: string): Record<string, any> | null {
  const t = text.trim()
  if (!t.startsWith('{')) return null
  try {
    return JSON.parse(t)
  } catch {
    try {
      return readPyLiteral(t)
    } catch {
      return null
    }
  }
}

const ID = /^[A-Za-z0-9_-]{11}$/

/** The 11-character video id from a YouTube link (watch, youtu.be, shorts, embed, live) or a bare id. */
export function videoIdFrom(input: string): string | null {
  const v = input.trim()
  if (!v) return null
  if (ID.test(v)) return v
  let u: URL
  try {
    u = new URL(/^https?:\/\//i.test(v) ? v : `https://${v}`)
  } catch {
    return null
  }
  const host = u.hostname.replace(/^(www|m|music)\./, '')
  if (host === 'youtu.be') {
    const id = u.pathname.split('/')[1] ?? ''
    return ID.test(id) ? id : null
  }
  if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
    const q = u.searchParams.get('v')
    if (q && ID.test(q)) return q
    const parts = u.pathname.split('/').filter(Boolean)
    if (['shorts', 'embed', 'live', 'v'].includes(parts[0]) && parts[1] && ID.test(parts[1])) return parts[1]
  }
  return null
}

export function clock(sec: number): string {
  const total = Math.max(0, Math.floor(sec))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const ss = `${s < 10 ? '0' : ''}${s}`
  return h ? `${h}:${m < 10 ? '0' : ''}${m}:${ss}` : `${m}:${ss}`
}
