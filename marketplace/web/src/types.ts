export interface GatewayHealth {
  ok: boolean
  round: number
}

export interface PassTerms {
  scope: string
  price: number
}

export interface PassesConfig {
  days: number
  note_prefix?: string
}

export interface GatewayConfig {
  network: string
  genesisHash: string
  algodUrl: string
  indexerUrl: string
  kmdUrl: string
  token: string
  assets: Record<string, number>
  treasury: string
  passes: PassesConfig
}

export interface VendorInfo {
  id: string
  name: string
  address: string
  listings: number
  domains: string[]
  asset: string
  pass?: PassTerms | null
  earnings: Record<string, number>
}

export interface ToolSchemaProperty {
  type?: string
  description?: string
  enum?: string[]
  items?: {
    type?: string
    enum?: string[]
  }
  default?: any
}

export interface ToolInputSchema {
  type?: string
  properties?: Record<string, ToolSchemaProperty>
  required?: string[]
  description?: string
}

export interface ToolInfo {
  name: string
  description?: string
  inputSchema?: ToolInputSchema
  price: number
}

export interface ListingVendor {
  id: string
  name: string
  address: string
}

export interface Listing {
  id: string
  domain: string
  proxy_index?: number
  vendor: ListingVendor
  asset: string
  port: number
  online: boolean
  tools: ToolInfo[]
  prices?: Record<string, number>
  pass?: PassTerms | null
}

export interface CallResultContent {
  type?: string
  text?: string
}

export interface CallResult {
  content: CallResultContent[]
  isError?: boolean
}

export interface PaymentDetails {
  txid: string | null
  amount: number
  asset: string
  payTo: string
}

export interface CallSuccessResponse {
  status: 200
  result: CallResult
  payment?: PaymentDetails
}

export interface CallPaymentRequiredResponse {
  status: 402
  paymentRequired: any
  header: string
}

export type CallResponse = CallSuccessResponse | CallPaymentRequiredResponse

export interface UploadResponse {
  path: string
}

export interface FaucetResponse {
  ok: boolean
  message?: string
}

export interface PassQuote {
  scope: string
  kind: 'service' | 'vendor'
  label: string
  price: number
  asset: string
  assetId: number
  days: number
  fee: number
  vendor: { id: string; name: string; address: string }
  txn: string
  signIndexes: number[]
}

export interface ActivePass {
  scope: string
  kind: 'service' | 'vendor'
  vendor: { id: string; name: string }
  asset: string
  amount: number
  txid: string
  purchasedAt: number
  expiresAt: number
  listing?: { id: string; domain: string }
}

export interface HistoryItem {
  txid: string
  round: number
  time: number
  amount: number
  asset: string
  to: string
  vendor?: string
  kind?: 'call' | 'pass'
  scope?: string
  listing?: string
  tool?: string
}

export interface BlockHeaderItem {
  round: number
  hash: string
  prevHash: string
  time: number
  txCount: number
}

export interface BlockTxnItem {
  txid: string
  type: string
  from: string
  to: string
  amount: number
  asset: string | number
  fee: number
  note?: string
  group?: string
}

export interface BlockDetail {
  round: number
  hash: string
  prevHash: string
  hashOk: boolean
  txns: BlockTxnItem[]
}

export interface ChainVerifyResponse {
  checked: number
  broken: any[]
}
