/**
 * Utility functions for formatting amounts, prices, addresses, and dates.
 */

export function formatAmount(baseUnits: number | string | bigint, decimals: number = 6): string {
  const num = typeof baseUnits === 'bigint' ? Number(baseUnits) : Number(baseUnits)
  if (isNaN(num)) return '0'
  const val = num / Math.pow(10, decimals)
  // Format with up to `decimals` fraction digits, stripping unnecessary trailing zeros
  return val.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })
}

export function formatPriceLabel(baseUnits: number | string | bigint, asset: string = 'ALGO'): string {
  const decimals = 6 // ALGO and mUSD both have 6 decimals
  const formatted = formatAmount(baseUnits, decimals)
  return `${formatted} ${asset}`
}

export function shortenAddress(address: string, chars: number = 4): string {
  if (!address) return ''
  if (address.length <= chars * 2 + 3) return address
  return `${address.slice(0, chars)}...${address.slice(-chars)}`
}

export function formatTimestamp(ts: number): string {
  if (!ts) return ''
  // If timestamp is in seconds, convert to milliseconds
  const ms = ts < 1e11 ? ts * 1000 : ts
  const d = new Date(ms)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function resolveAssetName(
  asset: string | number | undefined | null,
  assetsMap?: Record<string, number>
): string {
  if (asset === undefined || asset === null || asset === '' || asset === 0 || asset === '0') {
    return 'ALGO'
  }
  const str = String(asset).trim()
  if (str === '0') return 'ALGO'

  if (assetsMap) {
    if (assetsMap[str] !== undefined) {
      return str
    }
    const num = Number(str)
    if (!isNaN(num)) {
      for (const [name, id] of Object.entries(assetsMap)) {
        if (id === num) {
          return name
        }
      }
    }
  } else {
    if (str === '3456') return 'mUSD'
    if (str === '1010') return 'AI-SUB'
  }
  return str
}
