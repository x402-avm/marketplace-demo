/**
 * Plain-language names for the sixteen service domains, grouped the way a buyer looks for them.
 */
export interface DomainInfo {
  domain: string
  title: string
  summary: string
  category: string
}

export const CATEGORIES = ['Speech and sound', 'Images and video', 'Documents', 'Research and the web', 'Code'] as const

const LIST: DomainInfo[] = [
  { domain: 'tts', title: 'Text to speech', summary: 'Reads text aloud and returns a WAV file.', category: 'Speech and sound' },
  { domain: 'image_gen', title: 'Image generation', summary: 'Draws a new image from a prompt, or edits one you upload.', category: 'Images and video' },
  { domain: 'image_edit_mcp', title: 'Image editing', summary: 'Resizes, compresses and converts images.', category: 'Images and video' },
  { domain: 'video_edit_mcp', title: 'Video trimming', summary: 'Cuts a clip out of a video file.', category: 'Images and video' },
  { domain: 'ocr_mcp', title: 'Text recognition', summary: 'Reads text, QR codes and maths out of images and scans.', category: 'Images and video' },
  { domain: 'pdf_mcp', title: 'PDF reading', summary: 'Pulls the text and structure out of a PDF.', category: 'Documents' },
  { domain: 'pdf_reader_mcp', title: 'PDF evidence', summary: 'Reads PDFs and quotes the passages that answer a question.', category: 'Documents' },
  { domain: 'conversion_mcp', title: 'File conversion', summary: 'Converts documents, images, audio, video, data and archives.', category: 'Documents' },
  { domain: 'latex_mcp', title: 'LaTeX to PDF', summary: 'Compiles LaTeX source into a finished PDF.', category: 'Documents' },
  { domain: 'invoice_mcp', title: 'Invoices', summary: 'Builds an itemised invoice as a PDF.', category: 'Documents' },
  { domain: 'resume_mcp', title: 'Resumes', summary: 'Scores a resume and renders it as a PDF or web page.', category: 'Documents' },
  { domain: 'paper_mcp', title: 'Paper search', summary: 'Searches arXiv and returns matching papers.', category: 'Research and the web' },
  { domain: 'web_mcp', title: 'Web browsing', summary: 'Opens pages, takes screenshots and calls public APIs.', category: 'Research and the web' },
  { domain: 'domain_mcp', title: 'Domain lookup', summary: 'WHOIS, DNS, certificate and IP lookups for a domain.', category: 'Research and the web' },
  { domain: 'yt_mcp', title: 'YouTube', summary: 'Fetches transcripts and downloads videos.', category: 'Research and the web' },
  { domain: 'sandbox_mcp', title: 'Code sandbox', summary: 'Runs Python, JavaScript, C, C++ or Java in isolation.', category: 'Code' },
]

export const DOMAINS: Record<string, DomainInfo> = Object.fromEntries(LIST.map((d) => [d.domain, d]))

export function domainInfo(domain: string): DomainInfo {
  return DOMAINS[domain] ?? { domain, title: domain, summary: '', category: 'Other' }
}
