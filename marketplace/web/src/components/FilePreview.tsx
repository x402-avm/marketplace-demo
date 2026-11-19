import React from 'react'
import { getFileUrl } from '../api'

interface FilePreviewProps {
  path: string
}

const KIND: [RegExp, 'image' | 'audio' | 'video' | 'pdf'][] = [
  [/\.(png|jpe?g|webp|gif|svg)$/i, 'image'],
  [/\.(mp3|wav|ogg)$/i, 'audio'],
  [/\.(mp4|webm|mov)$/i, 'video'],
  [/\.pdf$/i, 'pdf'],
]

/** A file the service produced, shown inline when the browser can play or display it. */
export const FilePreview: React.FC<FilePreviewProps> = ({ path }) => {
  if (!path) return null
  const clean = path.trim().replace(/^['"]|['"]$/g, '')
  const url = getFileUrl(clean)
  const name = clean.split('/').pop() || clean
  const kind = KIND.find(([re]) => re.test(clean))?.[1]

  return (
    <figure className="artifact">
      {kind === 'image' && <img src={url} alt={`Output ${name}`} className="artifact__media" />}
      {kind === 'audio' && <audio controls src={url} className="artifact__media" />}
      {kind === 'video' && <video controls src={url} className="artifact__media" />}
      <figcaption className="artifact__caption">
        <span className="hash">{name}</span>
        <a href={url} target="_blank" rel="noopener noreferrer">
          {kind === 'pdf' ? 'Open PDF' : 'Open file'}
        </a>
      </figcaption>
    </figure>
  )
}
