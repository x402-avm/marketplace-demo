/** Readers for the resume service's plain-text answers (formats taken from servers/resume_mcp/runtime_server.py). */

export interface ScorePart {
  label: string
  points: number
  max: number
  detail: string
}
export interface Score {
  total: number
  parts: ScorePart[]
  penalty: { points: number; detail: string } | null
  tips: string[]
}

export function parseScore(text: string): Score | null {
  const m = text.match(/Resume Score:\s*(\d+)\s*\/\s*100/)
  if (!m) return null
  const parts: ScorePart[] = []
  let penalty: Score['penalty'] = null
  const tips: string[] = []
  let inTips = false
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (/^Tips:?$/i.test(line)) {
      inTips = true
      continue
    }
    if (inTips) {
      if (line.startsWith('- ')) tips.push(line.slice(2))
      continue
    }
    const pen = line.match(/^- Weak Phrases Penalty:\s*-(\d+) points?\s*\((.*)\)$/)
    if (pen) {
      penalty = { points: Number(pen[1]), detail: pen[2] }
      continue
    }
    const p = line.match(/^- (.+?):\s*(\d+)\/(\d+) points?\s*\((.*)\)$/)
    if (p) parts.push({ label: p[1], points: Number(p[2]), max: Number(p[3]), detail: p[4] })
  }
  return { total: Number(m[1]), parts, penalty, tips }
}

export interface Match {
  pct: number
  matched: string[]
  missing: string[]
}

const list = (s: string | undefined) =>
  !s || /^none$/i.test(s.trim())
    ? []
    : s
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean)

export function parseMatch(text: string): Match | null {
  const m = text.match(/ATS Match:\s*(\d+)%/)
  if (!m) return null
  return {
    pct: Number(m[1]),
    matched: list(text.match(/^Matched:\s*(.*)$/m)?.[1]),
    missing: list(text.match(/^Missing:\s*(.*)$/m)?.[1]),
  }
}

export function parseSuggestions(text: string): string[] {
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.startsWith('- '))
    .map((l) => l.slice(2))
}

export function findPath(text: string, ext: 'pdf' | 'html'): string | undefined {
  return text.match(new RegExp(`/[^\\s'"]+\\.${ext}`))?.[0]
}
