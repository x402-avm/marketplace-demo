import { describe, it, expect } from 'vitest'
import { formatAmount, formatPriceLabel, shortenAddress, formatTimestamp, resolveAssetName } from '../utils/format'

describe('Price and Amount Formatting', () => {
  it('formats ALGO with 6 decimals', () => {
    // 5 ALGO = 5,000,000 microAlgos
    expect(formatPriceLabel(5000000, 'ALGO')).toBe('5 ALGO')
    // 0.005 ALGO = 5,000 microAlgos
    expect(formatPriceLabel(5000, 'ALGO')).toBe('0.005 ALGO')
    // 1 microAlgo
    expect(formatPriceLabel(1, 'ALGO')).toBe('0.000001 ALGO')
    // 0 ALGO
    expect(formatPriceLabel(0, 'ALGO')).toBe('0 ALGO')
    // 10.5 ALGO = 10,500,000 microAlgos
    expect(formatPriceLabel(10500000, 'ALGO')).toBe('10.5 ALGO')
  })

  it('formats mUSD with 6 decimals', () => {
    // 100 mUSD = 100,000,000 base units
    expect(formatPriceLabel(100000000, 'mUSD')).toBe('100 mUSD')
    // 1.25 mUSD = 1,250,000 base units
    expect(formatPriceLabel(1250000, 'mUSD')).toBe('1.25 mUSD')
    // 0.50 mUSD = 500,000 base units
    expect(formatPriceLabel(500000, 'mUSD')).toBe('0.5 mUSD')
  })

  it('formats base amounts with formatAmount', () => {
    expect(formatAmount(1000000)).toBe('1')
    expect(formatAmount(1500000)).toBe('1.5')
    expect(formatAmount('6000')).toBe('0.006')
    expect(formatAmount(0)).toBe('0')
    expect(formatAmount(NaN)).toBe('0')
  })

  it('shortens Algorand addresses appropriately', () => {
    const addr = 'AOGPMJXDLFCQ4ZQAYGVCTKVRTKZWURYYPQRET3AIBJ3VTVEYRIHCB2E5KM'
    expect(shortenAddress(addr, 4)).toBe('AOGP...E5KM')
    expect(shortenAddress(addr, 6)).toBe('AOGPMJ...B2E5KM')
    expect(shortenAddress('')).toBe('')
    expect(shortenAddress('SHORT')).toBe('SHORT')
  })

  it('formats timestamps correctly', () => {
    expect(formatTimestamp(0)).toBe('')
    // Seconds timestamp
    const tsSec = 1700000000
    expect(formatTimestamp(tsSec)).toBeTruthy()
    // Milliseconds timestamp
    const tsMs = 1700000000000
    expect(formatTimestamp(tsMs)).toBeTruthy()
  })

  it('resolves asset names correctly from id or name', () => {
    const assetsMap = { ALGO: 0, mUSD: 3456, 'AI-SUB': 1010 }
    expect(resolveAssetName(0, assetsMap)).toBe('ALGO')
    expect(resolveAssetName('0', assetsMap)).toBe('ALGO')
    expect(resolveAssetName(undefined, assetsMap)).toBe('ALGO')
    expect(resolveAssetName(null, assetsMap)).toBe('ALGO')
    expect(resolveAssetName('', assetsMap)).toBe('ALGO')
    expect(resolveAssetName('ALGO', assetsMap)).toBe('ALGO')
    expect(resolveAssetName(3456, assetsMap)).toBe('mUSD')
    expect(resolveAssetName('3456', assetsMap)).toBe('mUSD')
    expect(resolveAssetName('mUSD', assetsMap)).toBe('mUSD')
    expect(resolveAssetName(1010, assetsMap)).toBe('AI-SUB')
    // Fallback without assetsMap
    expect(resolveAssetName(0)).toBe('ALGO')
    expect(resolveAssetName('0')).toBe('ALGO')
    expect(resolveAssetName('3456')).toBe('mUSD')
    expect(resolveAssetName('1010')).toBe('AI-SUB')
    expect(resolveAssetName('ALGO')).toBe('ALGO')
  })
})
