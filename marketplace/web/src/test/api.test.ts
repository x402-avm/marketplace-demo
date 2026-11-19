import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getHealth,
  getConfig,
  getVendors,
  getListings,
  getListing,
  callListing,
  uploadFile,
  faucet,
  getPassQuote,
  getPasses,
  getHistory,
  getBlocks,
  getBlock,
  getTx,
  verifyChain,
  getFileUrl,
} from '../api'

describe('API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('getHealth fetches /api/health', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, round: 42 }),
    }))

    const res = await getHealth()
    expect(fetch).toHaveBeenCalledWith('/api/health')
    expect(res).toEqual({ ok: true, round: 42 })
  })

  it('getConfig fetches /api/config', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ network: 'localnet', genesisHash: 'abc' }),
    }))

    const res = await getConfig()
    expect(fetch).toHaveBeenCalledWith('/api/config')
    expect(res.network).toBe('localnet')
  })

  it('getVendors fetches /api/vendors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: 'vendorA', name: 'Nova Labs' }],
    }))

    const res = await getVendors()
    expect(fetch).toHaveBeenCalledWith('/api/vendors')
    expect(res.length).toBe(1)
  })

  it('getListings builds URL with and without domain query', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }))

    await getListings()
    expect(fetch).toHaveBeenCalledWith('/api/listings')

    await getListings('tts')
    expect(fetch).toHaveBeenCalledWith('/api/listings?domain=tts')
  })

  it('getListing fetches /api/listings/:id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'tts-1', domain: 'tts' }),
    }))

    const res = await getListing('tts-1')
    expect(fetch).toHaveBeenCalledWith('/api/listings/tts-1')
    expect(res.id).toBe('tts-1')
  })

  it('callListing sends POST with correct body and headers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 200, result: { content: [{ text: 'done' }] } }),
    }))

    const res = await callListing('tts-1', {
      tool: 'synthesize_speech',
      args: { text: 'hello' },
      paymentSignature: 'sig123',
      identityTxn: 'id123',
    })

    expect(fetch).toHaveBeenCalledWith('/api/listings/tts-1/call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tool: 'synthesize_speech',
        args: { text: 'hello' },
        paymentSignature: 'sig123',
        identityTxn: 'id123',
      }),
    })
    expect(res.status).toBe(200)
  })

  it('callListing correctly parses 402 Payment Required response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 402,
      json: async () => ({
        status: 402,
        paymentRequired: { amount: 5000 },
        header: 'b64header',
      }),
    }))

    const res = await callListing('tts-1', {
      tool: 'synthesize_speech',
      args: { text: 'hello' },
    })

    expect(res.status).toBe(402)
    if (res.status === 402) {
      expect(res.paymentRequired.amount).toBe(5000)
      expect(res.header).toBe('b64header')
    }
  })

  it('uploadFile posts FormData to /api/upload', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ path: '/outputs/file.png' }),
    }))

    const file = new File(['content'], 'test.png', { type: 'image/png' })
    const res = await uploadFile(file)

    expect(fetch).toHaveBeenCalledWith('/api/upload', {
      method: 'POST',
      body: expect.any(FormData),
    })
    expect(res.path).toBe('/outputs/file.png')
  })

  it('getFileUrl creates proper URL', () => {
    expect(getFileUrl('/outputs/test.png')).toBe('/api/files?path=%2Foutputs%2Ftest.png')
  })

  it('faucet posts address to /api/faucet', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, message: 'dispensed' }),
    }))

    const res = await faucet('TESTADDR')
    expect(fetch).toHaveBeenCalledWith('/api/faucet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address: 'TESTADDR' }),
    })
    expect(res.ok).toBe(true)
  })

  it('getPassQuote posts address and scope to /api/passes/quote', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ scope: 'listing:tts-1', price: 1600000, txn: 'abc', signIndexes: [0] }),
    }))

    const res = await getPassQuote('TESTADDR', 'listing:tts-1')
    expect(fetch).toHaveBeenCalledWith('/api/passes/quote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address: 'TESTADDR', scope: 'listing:tts-1' }),
    })
    expect(res.signIndexes).toEqual([0])
  })

  it('getPasses fetches /api/passes/:address', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ scope: 'vendor:vendorA', txid: 'TX9' }],
    }))

    const res = await getPasses('ADDR123')
    expect(fetch).toHaveBeenCalledWith('/api/passes/ADDR123')
    expect(res[0].scope).toBe('vendor:vendorA')
  })

  it('getHistory fetches /api/history/:address', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ txid: 'TX1' }],
    }))

    const res = await getHistory('ADDR123')
    expect(fetch).toHaveBeenCalledWith('/api/history/ADDR123')
    expect(res.length).toBe(1)
  })

  it('getBlocks fetches /api/explorer/blocks with limit', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }))

    await getBlocks(10)
    expect(fetch).toHaveBeenCalledWith('/api/explorer/blocks?limit=10')
  })

  it('getBlock fetches /api/explorer/block/:round', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ round: 50, hash: 'H50' }),
    }))

    const res = await getBlock(50)
    expect(fetch).toHaveBeenCalledWith('/api/explorer/block/50')
    expect(res.round).toBe(50)
  })

  it('getTx fetches /api/explorer/tx/:txid', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ txid: 'TX99' }),
    }))

    const res = await getTx('TX99')
    expect(fetch).toHaveBeenCalledWith('/api/explorer/tx/TX99')
    expect(res.txid).toBe('TX99')
  })

  it('verifyChain builds query params for from and to', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ checked: 50, broken: [] }),
    }))

    await verifyChain(10, 20)
    expect(fetch).toHaveBeenCalledWith('/api/explorer/verify?from=10&to=20')
  })
})
