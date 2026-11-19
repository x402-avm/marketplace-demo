import { Buffer } from 'buffer'
if (typeof window !== 'undefined') {
  ;(window as any).Buffer = Buffer
  ;(window as any).global = window
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/schibsted-grotesk'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource-variable/newsreader/standard.css'
import '@fontsource-variable/newsreader/standard-italic.css'
import '@fontsource-variable/bricolage-grotesque/standard.css'
import '@fontsource-variable/hanken-grotesk'
import '@fontsource-variable/archivo/standard.css'
import '@fontsource-variable/jost'
import './styles/base.css'
import './styles/shell.css'
import './styles/home.css'
import './styles/vendors.css'
import './styles/listing.css'
import './styles/explorer.css'
import './styles/account.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
