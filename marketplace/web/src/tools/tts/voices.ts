/**
 * The voices installed on the Kokoro runtime (servers/tts/voices-v1.0.bin).
 * A voice id encodes accent and voice: the first letter is the accent, the second f (woman) or m (man).
 */
export const VOICE_IDS = [
  'af_alloy', 'af_aoede', 'af_bella', 'af_heart', 'af_jessica', 'af_kore', 'af_nicole', 'af_nova', 'af_river', 'af_sarah', 'af_sky',
  'am_adam', 'am_echo', 'am_eric', 'am_fenrir', 'am_liam', 'am_michael', 'am_onyx', 'am_puck', 'am_santa',
  'bf_alice', 'bf_emma', 'bf_isabella', 'bf_lily', 'bm_daniel', 'bm_fable', 'bm_george', 'bm_lewis',
  'ef_dora', 'em_alex', 'em_santa', 'ff_siwis', 'hf_alpha', 'hf_beta', 'hm_omega', 'hm_psi', 'if_sara', 'im_nicola',
  'jf_alpha', 'jf_gongitsune', 'jf_nezumi', 'jf_tebukuro', 'jm_kumo', 'pf_dora', 'pm_alex', 'pm_santa',
  'zf_xiaobei', 'zf_xiaoni', 'zf_xiaoxiao', 'zf_xiaoyi', 'zm_yunjian', 'zm_yunxi', 'zm_yunxia', 'zm_yunyang',
] as const

export const DEFAULT_VOICE = 'af_heart'

const ACCENTS: Record<string, string> = {
  a: 'American',
  b: 'British',
  e: 'Spanish',
  f: 'French',
  h: 'Hindi',
  i: 'Italian',
  j: 'Japanese',
  p: 'Brazilian Portuguese',
  z: 'Mandarin',
}

export interface Voice {
  id: string
  name: string
  accent: string
  /** 'Woman' or 'Man' */
  kind: string
}

export function describeVoice(id: string): Voice {
  const [code, raw = id] = id.split('_')
  const accent = ACCENTS[code?.[0] ?? ''] ?? 'Other'
  const kind = code?.[1] === 'm' ? 'Man' : 'Woman'
  const name = raw.charAt(0).toUpperCase() + raw.slice(1)
  return { id, name, accent, kind }
}

export interface VoiceGroup {
  title: string
  note?: string
  voices: Voice[]
}

export function voiceGroups(): VoiceGroup[] {
  const all = VOICE_IDS.map(describeVoice)
  return [
    { title: 'American English', voices: all.filter((v) => v.accent === 'American') },
    { title: 'British English', voices: all.filter((v) => v.accent === 'British') },
    {
      title: 'Other accents',
      note: 'These voices were trained on other languages. The script is still read as English, with their accent.',
      voices: all.filter((v) => v.accent !== 'American' && v.accent !== 'British'),
    },
  ]
}
