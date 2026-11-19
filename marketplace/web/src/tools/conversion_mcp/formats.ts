/**
 * What the conversion service really accepts (servers/conversion_mcp/runtime_server.py).
 * The lists are the server's own; keep them in step with it.
 */
export type ConvertTool = 'document_convert' | 'data_convert' | 'image_convert' | 'audio_convert' | 'video_convert'

interface Family {
  tool: ConvertTool
  kind: string
  from: string[]
  to: string[]
}

const FAMILIES: Family[] = [
  { tool: 'document_convert', kind: 'Document', from: ['html', 'htm', 'txt', 'md', 'doc', 'docx', 'odt', 'rtf', 'pptx', 'xlsx'], to: ['pdf', 'docx', 'odt', 'html', 'txt'] },
  { tool: 'data_convert', kind: 'Table data', from: ['json', 'csv', 'xlsx'], to: ['json', 'csv', 'xlsx'] },
  { tool: 'image_convert', kind: 'Image', from: ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff'], to: ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff'] },
  { tool: 'audio_convert', kind: 'Audio', from: ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac'], to: ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac'] },
  { tool: 'video_convert', kind: 'Video', from: ['mp4', 'webm', 'mkv', 'mov', 'gif'], to: ['mp4', 'webm', 'mkv', 'mov', 'gif'] },
]

export const ARCHIVE_FORMATS = ['zip', 'tar', 'tar.gz', '7z']

export const ARCHIVE_NAMES: Record<string, string> = {
  zip: 'Zip, opens anywhere',
  tar: 'Tar, plain bundle',
  'tar.gz': 'Tar, compressed',
  '7z': '7-Zip, smallest',
}

const NAMES: Record<string, string> = {
  pdf: 'PDF document',
  docx: 'Word document',
  odt: 'OpenDocument text',
  html: 'Web page',
  htm: 'Web page',
  txt: 'Plain text',
  md: 'Markdown',
  doc: 'Word document',
  rtf: 'Rich text',
  pptx: 'PowerPoint slides',
  xlsx: 'Excel spreadsheet',
  json: 'JSON data',
  csv: 'CSV table',
  png: 'PNG image',
  jpg: 'JPG image',
  jpeg: 'JPEG image',
  webp: 'WebP image',
  bmp: 'Bitmap image',
  gif: 'GIF',
  tiff: 'TIFF image',
  wav: 'WAV audio',
  mp3: 'MP3 audio',
  ogg: 'Ogg audio',
  flac: 'FLAC audio',
  m4a: 'M4A audio',
  aac: 'AAC audio',
  mp4: 'MP4 video',
  webm: 'WebM video',
  mkv: 'MKV video',
  mov: 'QuickTime video',
}

export const nameOf = (ext: string) => NAMES[ext] ?? `${ext.toUpperCase()} file`

/** The extension the service expects, from a file name or path. */
export function extOf(name: string): string {
  const base = name.split('/').pop() ?? name
  if (/\.tar\.gz$/i.test(base) || /\.tgz$/i.test(base)) return 'tar.gz'
  const m = /\.([A-Za-z0-9]+)$/.exec(base)
  const e = (m?.[1] ?? '').toLowerCase()
  return e === 'tif' ? 'tiff' : e
}

export interface Target {
  tool: ConvertTool
  to: string
  kind: string
}

/** Every conversion the service supports for this extension, and which tool performs it. */
export function targetsFor(ext: string): Target[] {
  const same = (a: string, b: string) => a === b || (a === 'jpg' && b === 'jpeg') || (a === 'jpeg' && b === 'jpg') || (a === 'htm' && b === 'html')
  const out: Target[] = []
  for (const f of FAMILIES) {
    if (!f.from.includes(ext)) continue
    for (const to of f.to) if (!same(ext, to)) out.push({ tool: f.tool, to, kind: f.kind })
  }
  return out
}

export function kindOf(ext: string): string {
  return FAMILIES.find((f) => f.from.includes(ext))?.kind ?? ''
}

/** Entries of a zip, read from its central directory without unpacking anything. */
export async function zipEntries(file: File): Promise<string[] | null> {
  try {
    const size = Math.min(file.size, 70000)
    const tail = new DataView(await file.slice(file.size - size).arrayBuffer())
    let eocd = -1
    for (let i = size - 22; i >= 0; i--) {
      if (tail.getUint32(i, true) === 0x06054b50) {
        eocd = i
        break
      }
    }
    if (eocd < 0) return null
    const count = tail.getUint16(eocd + 10, true)
    const dirSize = tail.getUint32(eocd + 12, true)
    const dirAt = tail.getUint32(eocd + 16, true)
    const dir = new DataView(await file.slice(dirAt, dirAt + dirSize).arrayBuffer())
    const dec = new TextDecoder()
    const names: string[] = []
    let p = 0
    for (let n = 0; n < count && p + 46 <= dir.byteLength; n++) {
      if (dir.getUint32(p, true) !== 0x02014b50) break
      const nl = dir.getUint16(p + 28, true)
      const xl = dir.getUint16(p + 30, true)
      const cl = dir.getUint16(p + 32, true)
      names.push(dec.decode(new Uint8Array(dir.buffer, p + 46, nl)))
      p += 46 + nl + xl + cl
    }
    return names.filter((x) => !x.endsWith('/'))
  } catch {
    return null
  }
}
