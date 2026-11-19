import algosdk from 'algosdk';

const ALGOD_TOKEN = 'a'.repeat(64);
const ALGOD_SERVER = 'http://localhost';
const ALGOD_PORT = 4001;

export const algod = new algosdk.Algodv2(ALGOD_TOKEN, ALGOD_SERVER, ALGOD_PORT);

let cachedAssetIds: { musdId: number; aisubId: number } | null = null;

export async function getAssetIds(): Promise<{ musdId: number; aisubId: number }> {
  if (cachedAssetIds) return cachedAssetIds;

  const res = await fetch('http://localhost:8800/api/config');
  if (!res.ok) {
    throw new Error(`Failed to fetch /api/config: ${res.status} ${res.statusText}`);
  }
  const cfg = await res.json();
  const musdId = Number(cfg.assets?.mUSD ?? 0);
  const aisubId = Number(cfg.assets?.['AI-SUB'] ?? cfg.subscription?.assetId ?? 0);

  cachedAssetIds = { musdId, aisubId };
  return cachedAssetIds;
}

export interface Balances {
  algo: number;
  musd: number;
  aisub: number;
}

export async function balances(address: string): Promise<Balances> {
  const { musdId, aisubId } = await getAssetIds();
  const accountInfo = await algod.accountInformation(address).do();

  // ALGO balance in microAlgos
  const algo = Number(accountInfo.amount || 0);

  let musd = 0;
  let aisub = 0;

  const assets: any[] = accountInfo.assets || [];
  for (const a of assets) {
    const assetId = Number(a.assetId || a['asset-id']);
    const amount = Number(a.amount || 0);
    if (assetId === musdId) {
      musd = amount;
    } else if (assetId === aisubId) {
      aisub = amount;
    }
  }

  return { algo, musd, aisub };
}

export interface TestAccount {
  account: algosdk.Account;
  mnemonic: string;
  address: string;
}

export function newAccount(): TestAccount {
  const account = algosdk.generateAccount();
  const mnemonic = algosdk.secretKeyToMnemonic(account.sk);
  const address = account.addr.toString();
  return { account, mnemonic, address };
}

export async function lookupTransaction(txid: string): Promise<any> {
  const token = 'a'.repeat(64);
  // Try indexer first, fallback to algod
  try {
    const res = await fetch(`http://localhost:8980/v2/transactions/${txid}`, {
      headers: { 'X-Indexer-API-Token': token },
    });
    if (res.ok) {
      const data = await res.json();
      if (data.transaction) return data.transaction;
    }
  } catch {
    // fallback
  }

  // Fallback to algod pending or confirmed
  try {
    const info = await algod.pendingTransactionInformation(txid).do();
    return info;
  } catch (e: any) {
    throw new Error(`Transaction ${txid} not found in indexer or algod: ${e.message}`);
  }
}
