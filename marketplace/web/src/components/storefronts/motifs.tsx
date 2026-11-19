import React from 'react'

export function seeded(seed: string) {
  let h = 2166136261
  for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619)
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507)
    h = Math.imul(h ^ (h >>> 13), 3266489909)
    h ^= h >>> 16
    return (h >>> 0) / 4294967296
  }
}

/** Nova: a star chart with graticule rings and a few joined stars. */
export const Constellation: React.FC<{ seed: string }> = ({ seed }) => {
  const r = seeded(seed)
  const stars = Array.from({ length: 9 }, () => ({ x: 30 + r() * 240, y: 25 + r() * 150, s: 1 + r() * 2.6 }))
  const dust = Array.from({ length: 40 }, () => ({ x: r() * 300, y: r() * 200, s: 0.4 + r() * 0.7 }))
  return (
    <svg viewBox="0 0 300 200" className="motif motif--constellation">
      <circle cx="150" cy="100" r="60" className="grat" />
      <circle cx="150" cy="100" r="110" className="grat" />
      <line x1="150" y1="0" x2="150" y2="200" className="grat" />
      <line x1="0" y1="100" x2="300" y2="100" className="grat" />
      {dust.map((d, i) => (
        <circle key={`d${i}`} cx={d.x} cy={d.y} r={d.s} className="dust" />
      ))}
      <polyline points={stars.map((s) => `${s.x},${s.y}`).join(' ')} className="join" />
      {stars.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.s} className="star" />
      ))}
    </svg>
  )
}

/** Blue Fern: a single frond, leaflets alternating and shrinking toward the tip. */
export const Frond: React.FC<{ seed?: string; leaves?: number }> = ({ leaves = 14 }) => {
  const parts: React.ReactNode[] = []
  for (let i = 0; i < leaves; i++) {
    const t = i / leaves
    const y = 190 - t * 170
    const x = 150 + Math.sin(t * 2.2) * 26
    const len = 62 * (1 - t * 0.78)
    const side = i % 2 === 0 ? 1 : -1
    const angle = side * (58 - t * 18)
    parts.push(
      <ellipse
        key={i}
        cx={x + side * len * 0.5}
        cy={y - len * 0.18}
        rx={len * 0.5}
        ry={len * 0.13 + 2}
        transform={`rotate(${-angle} ${x} ${y})`}
        className="leaf"
      />,
    )
  }
  const stem = Array.from({ length: 20 }, (_, i) => {
    const t = i / 19
    return `${150 + Math.sin(t * 2.2) * 26},${196 - t * 182}`
  }).join(' ')
  return (
    <svg viewBox="0 0 300 200" className="motif motif--frond">
      {parts}
      <polyline points={stem} className="stem" />
    </svg>
  )
}

/** Quarry: bands of rock, each a different grade. */
export const Strata: React.FC<{ seed: string }> = ({ seed }) => {
  const r = seeded(seed)
  const bands = ['#c7923e', '#6b7480', '#a2462c', '#d8c39a', '#3b4148', '#b9a37c']
  let y = 40
  return (
    <svg viewBox="0 0 300 200" className="motif motif--strata" preserveAspectRatio="none">
      {bands.map((c, i) => {
        const h = 14 + r() * 22
        const top = y
        y += h
        const wob = (k: number) => (r() - 0.5) * k
        const d = `M0 ${top + wob(6)} C 80 ${top + wob(14)}, 200 ${top + wob(14)}, 300 ${top + wob(6)} L300 ${y + 4} L0 ${y + 4} Z`
        return <path key={i} d={d} fill={c} />
      })}
    </svg>
  )
}

/** Lumen: a lamp's pool of light. */
export const Glow: React.FC<{ seed?: string }> = () => (
  <svg viewBox="0 0 300 200" className="motif motif--glow">
    <defs>
      <radialGradient id="lumen-pool" cx="50%" cy="46%" r="50%">
        <stop offset="0%" stopColor="#fff6c9" />
        <stop offset="45%" stopColor="#ffe17a" stopOpacity="0.85" />
        <stop offset="100%" stopColor="#ffe17a" stopOpacity="0" />
      </radialGradient>
    </defs>
    <circle cx="150" cy="92" r="96" fill="url(#lumen-pool)" />
    <circle cx="150" cy="92" r="26" className="bulb" />
  </svg>
)
