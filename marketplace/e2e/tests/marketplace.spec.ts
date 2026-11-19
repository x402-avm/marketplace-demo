import { test, expect, Page } from '@playwright/test';
import { balances, newAccount, lookupTransaction, TestAccount } from '../helpers/chain';
import { connectMnemonic } from '../helpers/wallet';

test.describe.serial('AI Service Marketplace End-to-End Suite', () => {
  let user: TestAccount;
  let page: Page;
  let step3Txid = '';
  let step4Txid = '';
  let step3Round = 0;

  test.beforeAll(async ({ browser }) => {
    // Generate fresh test account
    user = newAccount();
    console.log(`[E2E Setup] Fresh account created: ${user.address}`);
    page = await browser.newPage();
  });

  test.afterAll(async () => {
    if (page) {
      await page.close();
    }
  });

  // --------------------------------------------------------------------------
  // Step 1: Fresh account -> connect -> balance 0 -> faucet -> +10 ALGO
  // --------------------------------------------------------------------------
  test('1. Fresh account connect and faucet funding (+10 ALGO)', async () => {
    await page.goto('/wallet');

    // Connect via mnemonic prompt
    await connectMnemonic(page, user.mnemonic);

    // Assert initial on-chain balance is 0
    const initBal = await balances(user.address);
    expect(initBal.algo).toBe(0);
    console.log(`Step 1 Initial on-chain balance: ${initBal.algo} µA`);

    // UI shows 0 ALGO
    const balanceAlgo = page.getByTestId('balance-algo').first();
    await expect(balanceAlgo).toContainText('0 ALGO');

    // Request test funds via faucet
    const faucetBtn = page.getByTestId('faucet-btn');
    await expect(faucetBtn).toBeVisible();
    await faucetBtn.click();

    // Success alert
    await expect(page.getByTestId('notice')).toHaveClass(/notice--ok/, { timeout: 20_000 });

    // Assert on-chain balance increased by exactly 10 ALGO (10,000,000 µA)
    const afterBal = await balances(user.address);
    const delta = afterBal.algo - initBal.algo;
    console.log(`Step 1 Faucet delta: +${delta} µA (now ${afterBal.algo} µA)`);
    expect(delta).toBe(10_000_000);

    // UI balance updates to 10 ALGO
    await expect(balanceAlgo).toContainText('10 ALGO', { timeout: 15_000 });
  });

  // --------------------------------------------------------------------------
  // Step 2: Marketplace page lists 16 domains; tts comparison table shows 4 vendors
  // --------------------------------------------------------------------------
  test('2. Marketplace lists 16 domains and tts comparison shows 4 vendors with mUSD badge', async () => {
    await page.goto('/');

    // The directory lists all 16 services
    const services = page.locator('li[data-testid^="service-"]');
    await expect(services).toHaveCount(16, { timeout: 20_000 });

    // Open the text-to-speech entry
    const tts = page.getByTestId('service-tts');
    await expect(tts).toBeVisible();
    await tts.locator('button').click();

    // Verify comparison table appears with 4 vendors
    const table = page.getByTestId('comparison');
    await expect(table).toBeVisible();
    const rows = table.locator('tbody tr');
    await expect(rows).toHaveCount(4);

    // Check Blue Fern AI row has an mUSD badge
    const blueFernRow = table.locator('tr', { hasText: 'Blue Fern AI' });
    await expect(blueFernRow).toBeVisible();
    await expect(blueFernRow.getByTestId('asset')).toHaveText('mUSD');

    // Check Nova Labs row is present
    const novaLabsRow = table.locator('tr', { hasText: 'Nova Labs' });
    await expect(novaLabsRow).toBeVisible();
  });

  // --------------------------------------------------------------------------
  // Step 3: Pay ALGO on Nova Labs tts listing -> paid-txid, buyer -= price, vendorA += price - 2000
  // --------------------------------------------------------------------------
  test('3. Pay ALGO on Nova Labs tts listing (exact price, buyer fee 0, vendor pays fees)', async () => {
    // Navigate to Nova Labs tts listing (tts-1)
    await page.goto('/listing/tts-1');
    await expect(page.locator('h1')).toContainText('Text to speech');
    await expect(page.getByTestId('service-id')).toHaveText('tts-1');
    await expect(page.getByTestId('pay-run')).toBeVisible({ timeout: 20_000 });

    // Fetch listing config to get exact vendor address and tool price
    const res = await fetch('http://localhost:8800/api/listings/tts-1');
    const listing = await res.json();
    const vendorAAddr = listing.vendor?.address || 'A4ZN6Y7WO2SJ2NA33IERUZWC476MCMTX6JA5CM2XC27ZS2OIB43F24TCWE';
    const price = listing.tools?.[0]?.price ?? 20000; // 20,000 µA

    // Pre-execution on-chain balances
    const preBuyer = await balances(user.address);
    const preVendor = await balances(vendorAAddr);

    // Fill parameter and execute tool
    await page.getByTestId('field-text').fill('hello marketplace');
    await page.getByTestId('pay-run').click();

    // Wait for execution and settlement result
    const resultElem = page.getByTestId('result-text');
    await expect(resultElem).toBeVisible({ timeout: 60_000 });
    const resultText = await resultElem.innerText();
    expect(resultText).toContain('.wav');

    // Confirmation with paid-txid
    const paidElem = page.getByTestId('paid-txid');
    await expect(paidElem).toBeVisible();

    // Extract txid
    const txLink = paidElem.locator('a');
    const href = await txLink.getAttribute('href');
    step3Txid = (href || '').replace('/explorer/tx/', '').trim();
    expect(step3Txid).toBeTruthy();
    console.log(`Step 3 Payment TxID: ${step3Txid}`);

    // Assert exact on-chain deltas
    const postBuyer = await balances(user.address);
    const postVendor = await balances(vendorAAddr);

    const buyerDelta = preBuyer.algo - postBuyer.algo;
    const vendorDelta = postVendor.algo - preVendor.algo;
    console.log(`Step 3 Balance Deltas: buyer ALGO -${buyerDelta} µA, vendorA ALGO +${vendorDelta} µA`);

    // Buyer pays exact price (fee 0 for buyer)
    expect(buyerDelta).toBe(price);
    // Vendor receives price - 2000 (vendor covers 2000 µA pooled fee)
    expect(vendorDelta).toBe(price - 2000);

    // Verify txid exists on chain with receiver = vendorA
    const txInfo = await lookupTransaction(step3Txid);
    const receiver =
      txInfo?.['payment-transaction']?.receiver ||
      txInfo?.receiver ||
      txInfo?.payment?.receiver;
    step3Round = Number(txInfo?.['confirmed-round'] || txInfo?.confirmedRound || 0);
    expect(receiver).toBe(vendorAAddr);
  });

  // --------------------------------------------------------------------------
  // Step 4: Opt in mUSD -> faucet after 61s wait -> 100 mUSD -> Pay mUSD on Blue Fern AI
  // --------------------------------------------------------------------------
  test('4. Opt in mUSD, faucet 100 mUSD, pay mUSD on Blue Fern AI tts listing', async () => {
    await page.goto('/wallet');

    // Opt-in to mUSD
    const optinBtn = page.getByTestId('optin-musd');
    await expect(optinBtn).toBeVisible();
    await optinBtn.click();
    await expect(optinBtn).toBeHidden({ timeout: 20_000 });
    await expect(page.getByTestId('balance-musd')).not.toHaveText('not enabled', { timeout: 15_000 });

    // Faucet has a 60s rate limit. Wait 61 seconds for the window to reset
    console.log('[Step 4] Waiting 61 seconds for faucet rate limit reset...');
    await page.waitForTimeout(61_000);

    // Request faucet again (now dispenses 10 ALGO + 100 mUSD because opted-in)
    await page.getByTestId('faucet-btn').click();
    await expect(page.getByTestId('notice')).toHaveClass(/notice--ok/, { timeout: 20_000 });

    // Verify buyer now has 100 mUSD (100,000,000 base units)
    const bAfterFaucet = await balances(user.address);
    console.log(`Step 4 Balances after 2nd faucet: ${bAfterFaucet.algo} µA, ${bAfterFaucet.musd} base units mUSD`);
    expect(bAfterFaucet.musd).toBe(100_000_000);

    // Open Blue Fern AI tts listing (tts-2, asset mUSD)
    await page.goto('/listing/tts-2');
    await expect(page.locator('h1')).toContainText('Text to speech');
    await expect(page.getByTestId('service-id')).toHaveText('tts-2');
    await expect(page.getByTestId('pay-run')).toBeVisible({ timeout: 20_000 });

    const res = await fetch('http://localhost:8800/api/listings/tts-2');
    const listing = await res.json();
    const vendorBAddr = listing.vendor?.address || 'DCOWE3GVBN4CZZCAQCWZFT32NMMCRI7Z75INX7NBWSS2ARO5QYVH7VJJDI';
    const price = listing.tools?.[0]?.price ?? 16000; // 16,000 mUSD base units

    const preBuyer = await balances(user.address);
    const preVendor = await balances(vendorBAddr);

    // Run tool with mUSD payment
    await page.getByTestId('field-text').fill('hello musd payment');
    await page.getByTestId('pay-run').click();

    // Verify result and paid-txid
    const resultElem = page.getByTestId('result-text');
    await expect(resultElem).toBeVisible({ timeout: 60_000 });
    const paidElem = page.getByTestId('paid-txid');
    await expect(paidElem).toBeVisible();

    const txLink = paidElem.locator('a');
    const href = await txLink.getAttribute('href');
    step4Txid = (href || '').replace('/explorer/tx/', '').trim();
    expect(step4Txid).toBeTruthy();
    console.log(`Step 4 Payment TxID: ${step4Txid}`);

    // Assert exact on-chain deltas
    const postBuyer = await balances(user.address);
    const postVendor = await balances(vendorBAddr);

    const buyerDelta = preBuyer.musd - postBuyer.musd;
    const vendorDelta = postVendor.musd - preVendor.musd;
    console.log(`Step 4 mUSD Deltas: buyer -${buyerDelta}, vendorB +${vendorDelta}`);

    expect(buyerDelta).toBe(price);
    expect(vendorDelta).toBe(price);
  });

  // --------------------------------------------------------------------------
  // Step 5: Tool error is not charged: sandbox listing, language "cobol" -> "not charged"
  // --------------------------------------------------------------------------
  test('5. Tool error is not charged (cobol language in sandbox_mcp)', async () => {
    await page.goto('/listing/sandbox_mcp-1');
    await expect(page.locator('h1')).toContainText('Code sandbox');
    await expect(page.getByTestId('pay-run')).toBeVisible({ timeout: 20_000 });

    const preBuyer = await balances(user.address);

    // Select run_sandbox_code if needed
    if (await page.getByTestId('field-code').isVisible()) {
      await page.getByTestId('field-code').fill('DISPLAY "COBOL TEST"');
    }
    await page.getByTestId('field-language').fill('cobol');

    // Run tool
    await page.getByTestId('pay-run').click();

    // UI shows the error and "not charged"
    await expect(page.getByTestId('not-charged')).toContainText('not charged', { timeout: 30_000 });

    // Assert buyer on-chain balances are completely unchanged
    const postBuyer = await balances(user.address);
    console.log(
      `Step 5 Uncharged Deltas: ALGO delta ${postBuyer.algo - preBuyer.algo}, mUSD delta ${postBuyer.musd - preBuyer.musd}`
    );
    expect(postBuyer.algo).toBe(preBuyer.algo);
    expect(postBuyer.musd).toBe(preBuyer.musd);
  });

  // --------------------------------------------------------------------------
  // Step 5b: Code sandbox runs real code and charges exactly once
  // --------------------------------------------------------------------------
  test('5b. Code sandbox runs real code and charges exactly once', async () => {
    await page.goto('/listing/sandbox_mcp-1');
    await expect(page.locator('h1')).toContainText('Code sandbox');
    await expect(page.getByTestId('pay-run')).toBeVisible({ timeout: 20_000 });

    const res = await fetch('http://localhost:8800/api/listings/sandbox_mcp-1');
    const listing = await res.json();
    const runTool = listing.tools?.find((t: any) => t.name === 'run_sandbox_code');
    const expectedPrice: number = runTool ? runTool.price : (listing.prices?.run_sandbox_code ?? 5000);

    const preBuyer = await balances(user.address);

    await page.getByTestId('field-language').fill('python');
    await page.getByTestId('field-code').fill('print(sum(range(10)))');

    await page.getByTestId('pay-run').click();

    const resultElem = page.getByTestId('result-text');
    await expect(resultElem).toBeVisible({ timeout: 60_000 });
    await expect(resultElem).toContainText('45', { timeout: 60_000 });

    const paidElem = page.getByTestId('paid-txid');
    await expect(paidElem).toBeVisible({ timeout: 20_000 });

    const postBuyer = await balances(user.address);
    const buyerAlgoDelta = preBuyer.algo - postBuyer.algo;
    console.log(`Step 5b Buyer ALGO Delta: ${buyerAlgoDelta} µA (expected: ${expectedPrice} µA)`);
    expect(buyerAlgoDelta).toBe(expectedPrice);
  });

  // --------------------------------------------------------------------------
  // Step 6: Passes are individual. Buy Quarry's pass for its tts service -> that call is free;
  //         the same wallet still pays Nova Labs for Nova's tts.
  // --------------------------------------------------------------------------
  test('6. A pass covers one vendor and one service only', async () => {
    const quarry = await (await fetch('http://localhost:8800/api/listings/tts-3')).json();
    const nova = await (await fetch('http://localhost:8800/api/listings/tts-1')).json();
    const passPrice: number = quarry.pass.price;
    const novaPrice: number = nova.tools?.[0]?.price ?? 20000;

    await page.goto('/listing/tts-3');
    await expect(page.locator('h1')).toContainText('Text to speech');
    await expect(page.getByTestId('pay-run')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('pass-active')).toBeHidden();

    const preBuy = await balances(user.address);
    const preQuarry = await balances(quarry.vendor.address);
    await page.getByTestId('service-pass-buy').click();
    await expect(page.getByTestId('service-pass-status')).toContainText('Active until', { timeout: 45_000 });

    const postBuy = await balances(user.address);
    const postQuarry = await balances(quarry.vendor.address);
    console.log(`Step 6 Pass purchase: buyer ALGO -${preBuy.algo - postBuy.algo} µA, Quarry +${postQuarry.algo - preQuarry.algo} µA`);
    expect(preBuy.algo - postBuy.algo).toBe(passPrice + 1000); // price + the buyer's own network fee
    expect(postQuarry.algo - preQuarry.algo).toBe(passPrice); // paid straight to the vendor

    // the call on Quarry's tts is now free
    await expect(page.getByTestId('pass-active')).toBeVisible({ timeout: 15_000 });
    const preFree = await balances(user.address);
    await page.getByTestId('field-text').fill('free pass holder voice call');
    await page.getByTestId('pay-run').click();
    await expect(page.getByTestId('result-text')).toContainText('.wav', { timeout: 60_000 });
    await expect(page.getByTestId('covered-by-pass')).toBeVisible();
    await expect(page.getByTestId('paid-txid')).toBeHidden();
    const postFree = await balances(user.address);
    console.log(`Step 6 Pass call: buyer ALGO delta ${postFree.algo - preFree.algo}`);
    expect(postFree.algo).toBe(preFree.algo);
    expect(postFree.musd).toBe(preFree.musd);

    // the same wallet still pays Nova Labs: the Quarry pass does not travel
    await page.goto('/listing/tts-1');
    await expect(page.getByTestId('pay-run')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('pass-active')).toBeHidden();
    const preNova = await balances(user.address);
    await page.getByTestId('field-text').fill('nova still charges');
    await page.getByTestId('pay-run').click();
    await expect(page.getByTestId('paid-txid')).toBeVisible({ timeout: 60_000 });
    const postNova = await balances(user.address);
    console.log(`Step 6 Nova call with a Quarry pass: buyer ALGO -${preNova.algo - postNova.algo} µA`);
    expect(preNova.algo - postNova.algo).toBe(novaPrice);
  });

  // --------------------------------------------------------------------------
  // Step 7: History page shows rows with txids of steps 3 & 4. Explorer hash-ok badge.
  // --------------------------------------------------------------------------
  test('7. History page shows past payment txids and Explorer block shows hash-ok badge', async () => {
    await page.goto('/history');

    // Wait for history table rows
    const historyRows = page.getByTestId('history-row');
    await expect(historyRows.first()).toBeVisible({ timeout: 20_000 });

    // Assert both step 3 and step 4 txids are present in history
    expect(step3Txid).toBeTruthy();
    expect(step4Txid).toBeTruthy();
    await expect(page.locator(`a[href*="${step3Txid}"]`)).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(`a[href*="${step4Txid}"]`)).toBeVisible({ timeout: 15_000 });

    // Navigate to the block of step 3's txid
    if (!step3Round) {
      const txInfo = await lookupTransaction(step3Txid);
      step3Round = Number(txInfo?.['confirmed-round'] || txInfo?.confirmedRound || 0);
    }
    expect(step3Round).toBeGreaterThan(0);

    await page.goto(`/explorer/block/${step3Round}`);
    await expect(page.locator('h1')).toContainText(`Block #${step3Round}`);

    // Verify hash-ok badge is visible and valid
    const hashBadge = page.getByTestId('hash-ok');
    await expect(hashBadge).toBeVisible({ timeout: 15_000 });
    await expect(hashBadge).toHaveText(/matches/);
  });

  // --------------------------------------------------------------------------
  // Step 8: Negative test: second browser context with NEW unfunded account tries pay-run
  // --------------------------------------------------------------------------
  test('8. Negative: new unfunded account pay-run displays payment error, no result', async ({ browser }) => {
    // Isolated second browser context
    const context2 = await browser.newContext();
    const page2 = await context2.newPage();

    const unfundedUser = newAccount();
    console.log(`[Step 8] Unfunded account: ${unfundedUser.address}`);

    await page2.goto('/wallet');
    await connectMnemonic(page2, unfundedUser.mnemonic);

    await page2.goto('/listing/tts-1');
    await page2.getByTestId('field-text').fill('unfunded call test');
    await page2.getByTestId('pay-run').click();

    // UI shows payment error
    await expect(page2.getByTestId('call-error')).toBeVisible({ timeout: 20_000 });

    // No result delivered
    await expect(page2.getByTestId('result-text')).not.toBeVisible();

    await context2.close();
  });
});
