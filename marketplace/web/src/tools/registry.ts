import type React from 'react'
import type { ToolUIProps } from './kit'

/**
 * Every src/tools/<domain>/index.tsx registers itself; no shared file has to be edited to add one.
 * A domain without its own interface falls back to the generic form on the service page.
 */
type ToolModule = { domain: string; default: React.FC<ToolUIProps> }

const modules = import.meta.glob<ToolModule>('./*/index.tsx', { eager: true })

export const TOOL_UIS: Record<string, React.FC<ToolUIProps>> = Object.fromEntries(
  Object.values(modules)
    .filter((m) => m && m.domain && m.default)
    .map((m) => [m.domain, m.default]),
)
