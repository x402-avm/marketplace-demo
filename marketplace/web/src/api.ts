import type {
  GatewayHealth,
  GatewayConfig,
  VendorInfo,
  Listing,
  CallResponse,
  UploadResponse,
  FaucetResponse,
  PassQuote,
  ActivePass,
  HistoryItem,
  BlockHeaderItem,
  BlockDetail,
  ChainVerifyResponse,
} from './types'

const BASE_URL = '/api'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText
    try {
      const data = await res.json()
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(`API error (${res.status}): ${errorDetail}`)
  }
  return res.json() as Promise<T>
}

export async function getHealth(): Promise<GatewayHealth> {
  const res = await fetch(`${BASE_URL}/health`)
  return handleResponse<GatewayHealth>(res)
}

export async function getConfig(): Promise<GatewayConfig> {
  const res = await fetch(`${BASE_URL}/config`)
  return handleResponse<GatewayConfig>(res)
}

export async function getVendors(): Promise<VendorInfo[]> {
  const res = await fetch(`${BASE_URL}/vendors`)
  return handleResponse<VendorInfo[]>(res)
}

export async function getListings(domain?: string): Promise<Listing[]> {
  const url = domain ? `${BASE_URL}/listings?domain=${encodeURIComponent(domain)}` : `${BASE_URL}/listings`
  const res = await fetch(url)
  return handleResponse<Listing[]>(res)
}

export async function getListing(id: string): Promise<Listing> {
  const res = await fetch(`${BASE_URL}/listings/${encodeURIComponent(id)}`)
  return handleResponse<Listing>(res)
}

export async function callListing(
  id: string,
  req: { tool: string; args: Record<string, any>; paymentSignature?: string; identityTxn?: string }
): Promise<CallResponse> {
  const res = await fetch(`${BASE_URL}/listings/${encodeURIComponent(id)}/call`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  })

  if (res.status === 402) {
    const data = await res.json()
    return {
      status: 402,
      paymentRequired: data.paymentRequired,
      header: data.header,
    }
  }

  return handleResponse<CallResponse>(res)
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse<UploadResponse>(res)
}

export function getFileUrl(path: string): string {
  return `${BASE_URL}/files?path=${encodeURIComponent(path)}`
}

export async function faucet(address: string): Promise<FaucetResponse> {
  const res = await fetch(`${BASE_URL}/faucet`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ address }),
  })
  return handleResponse<FaucetResponse>(res)
}

export async function getPassQuote(address: string, scope: string): Promise<PassQuote> {
  const res = await fetch(`${BASE_URL}/passes/quote`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ address, scope }),
  })
  return handleResponse<PassQuote>(res)
}

export async function getPasses(address: string): Promise<ActivePass[]> {
  const res = await fetch(`${BASE_URL}/passes/${encodeURIComponent(address)}`)
  return handleResponse<ActivePass[]>(res)
}

export async function getHistory(address: string): Promise<HistoryItem[]> {
  const res = await fetch(`${BASE_URL}/history/${encodeURIComponent(address)}`)
  return handleResponse<HistoryItem[]>(res)
}

export async function getBlocks(limit: number = 20): Promise<BlockHeaderItem[]> {
  const res = await fetch(`${BASE_URL}/explorer/blocks?limit=${limit}`)
  return handleResponse<BlockHeaderItem[]>(res)
}

export async function getBlock(round: number): Promise<BlockDetail> {
  const res = await fetch(`${BASE_URL}/explorer/block/${round}`)
  return handleResponse<BlockDetail>(res)
}

export async function getTx(txid: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/explorer/tx/${encodeURIComponent(txid)}`)
  return handleResponse<any>(res)
}

export async function verifyChain(from?: number, to?: number): Promise<ChainVerifyResponse> {
  const params = new URLSearchParams()
  if (from !== undefined) params.set('from', String(from))
  if (to !== undefined) params.set('to', String(to))
  const qs = params.toString() ? `?${params.toString()}` : ''
  const res = await fetch(`${BASE_URL}/explorer/verify${qs}`)
  return handleResponse<ChainVerifyResponse>(res)
}
