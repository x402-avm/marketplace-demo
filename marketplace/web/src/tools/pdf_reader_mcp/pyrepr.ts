/**
 * The PDF services answer with the Python repr of an MCP result, e.g.
 *   {'content': [{'type': 'text', 'text': '{"full_text": ...}', ...}], 'isError': False}
 * These helpers read the quoted Python strings back so the JSON inside can be parsed.
 */
import { parseJson } from '../kit'

function readPyString(s: string, start: number): { value: string; end: number } | null {
  const q = s[start]
  if (q !== "'" && q !== '"') return null
  const parts: string[] = []
  let i = start + 1
  let from = i
  while (i < s.length) {
    const c = s[i]
    if (c === q) {
      parts.push(s.slice(from, i))
      return { value: parts.join(''), end: i + 1 }
    }
    if (c !== '\\') {
      i++
      continue
    }
    parts.push(s.slice(from, i))
    const n = s[i + 1]
    let step = 2
    switch (n) {
      case 'n': parts.push('\n'); break
      case 't': parts.push('\t'); break
      case 'r': parts.push('\r'); break
      case '\\': parts.push('\\'); break
      case "'": parts.push("'"); break
      case '"': parts.push('"'); break
      case 'x': parts.push(String.fromCharCode(parseInt(s.slice(i + 2, i + 4), 16))); step = 4; break
      case 'u': parts.push(String.fromCharCode(parseInt(s.slice(i + 2, i + 6), 16))); step = 6; break
      case 'U': parts.push(String.fromCodePoint(parseInt(s.slice(i + 2, i + 10), 16))); step = 10; break
      default: parts.push('\\' + (n ?? ''))
    }
    i += step
    from = i
  }
  return null
}

/** Every text item inside a Python-repr MCP result. */
export function pyTexts(s: string): string[] {
  const out: string[] = []
  const re = /'type': 'text', 'text': /g
  let m: RegExpExecArray | null
  while ((m = re.exec(s))) {
    const r = readPyString(s, m.index + m[0].length)
    if (!r) break
    out.push(r.value)
    re.lastIndex = r.end
  }
  return out
}

/** Every image item (base64 data and mime type) inside a Python-repr MCP result. */
export function pyImages(s: string): { data: string; mime: string }[] {
  const out: { data: string; mime: string }[] = []
  const re = /'type': 'image', 'data': /g
  let m: RegExpExecArray | null
  while ((m = re.exec(s))) {
    const r = readPyString(s, m.index + m[0].length)
    if (!r) break
    const mime = /^, 'mimeType': '([^']+)'/.exec(s.slice(r.end, r.end + 60))?.[1] ?? 'image/png'
    out.push({ data: r.value, mime })
    re.lastIndex = r.end
  }
  return out
}

/** The JSON objects a PDF service returned, whether it answered with plain JSON or a Python repr. */
export function payloads(text: string): any[] {
  const direct = parseJson(text)
  if (direct) return [direct]
  return pyTexts(text)
    .map((t) => parseJson(t))
    .filter((x) => x !== null)
}
