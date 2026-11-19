import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { balances, newAccount, lookupTransaction, algod, TestAccount } from '../helpers/chain';
import { connectMnemonic } from '../helpers/wallet';

interface LayoutCheckResult {
  horizontalScroll: boolean;
  scrollWidth: number;
  innerWidth: number;
  overflowOffenders: string[];
  contrastOffenders: Array<{
    tag: string;
    text: string;
    color: string;
    bg: string;
    contrast: number;
  }>;
}

interface PageCheckSummary {
  page: string;
  width: number;
  scheme: 'light' | 'dark';
  noHorizontalScroll: boolean;
  noOverflow: boolean;
  contrastPass: boolean;
  consoleErrorsCount: number;
  screenshotFile: string;
}

const checkSummaries: PageCheckSummary[] = [];

test.describe.serial('@screens UI Screenshots and Layout Suite', () => {
  let user: TestAccount;
  let page: Page;
  let consoleErrors: string[] = [];
  let paidTxid = '';
  let confirmedRound = 0;

  const SCREENSHOTS_DIR = path.resolve(__dirname, '../screenshots');

  test.beforeAll(async ({ browser }) => {
    if (!fs.existsSync(SCREENSHOTS_DIR)) {
      fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
    }

    user = newAccount();
    console.log(`[Screens Setup] Fresh account created: ${user.address}`);

    page = await browser.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        consoleErrors.push(text);
        console.warn(`[Browser Console Error] ${text}`);
      }
    });

    page.on('pageerror', (err) => {
      consoleErrors.push(err.message);
      console.warn(`[Browser Page Error] ${err.message}`);
    });

    // Connect wallet and fund via faucet (+10 ALGO)
    await page.goto('/wallet');
    await connectMnemonic(page, user.mnemonic);

    const balanceAlgo = page.getByTestId('balance-algo').first();
    const faucetBtn = page.getByTestId('faucet-btn');
    await expect(faucetBtn).toBeVisible({ timeout: 15_000 });
    await faucetBtn.click();
    await expect(page.getByTestId('notice')).toHaveClass(/notice--ok/, { timeout: 20_000 });
    await expect(balanceAlgo).toContainText('10 ALGO', { timeout: 15_000 });
    console.log('[Screens Setup] Faucet funded 10 ALGO successfully');
  });

  test.afterAll(async () => {
    if (page) {
      await page.close();
    }

    // Print summary table to console
    console.log('\n========================= SCREENSHOTS & LAYOUT SUMMARY =========================');
    console.log(
      '| Page | Size | Theme | No H-Scroll | No Overflow | Contrast >=4.5 | Console Errs | File |'
    );
    console.log(
      '|---|---|---|---|---|---|---|---|'
    );
    for (const s of checkSummaries) {
      const hScroll = s.noHorizontalScroll ? 'PASS' : 'FAIL';
      const overflow = s.noOverflow ? 'PASS' : 'FAIL';
      const contrast = s.contrastPass ? 'PASS' : 'FAIL';
      console.log(
        `| ${s.page} | ${s.width}px | ${s.scheme} | ${hScroll} | ${overflow} | ${contrast} | ${s.consoleErrorsCount} | ${s.screenshotFile} |`
      );
    }
    console.log('=================================================================================\n');
  });

  async function runLayoutChecks(p: Page, vw: number): Promise<LayoutCheckResult> {
    return await p.evaluate((width) => {
      const scrollWidth = document.documentElement.scrollWidth;
      const innerWidth = window.innerWidth;
      const horizontalScroll = Math.ceil(scrollWidth) > innerWidth;

      const overflowOffenders: string[] = [];
      if (width <= 400) {
        const allEls = document.querySelectorAll('*');
        for (const el of Array.from(allEls)) {
          if (
            ['SCRIPT', 'STYLE', 'HEAD', 'META', 'TITLE', 'NOSCRIPT', 'HTML', 'BODY'].includes(
              el.tagName
            )
          ) {
            continue;
          }

          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            let isContainedInScroll = false;
            let parent = el.parentElement;
            while (parent && parent !== document.body && parent !== document.documentElement) {
              const pStyle = window.getComputedStyle(parent);
              if (['auto', 'scroll', 'hidden'].includes(pStyle.overflowX)) {
                isContainedInScroll = true;
                break;
              }
              parent = parent.parentElement;
            }

            if (!isContainedInScroll && rect.right > innerWidth + 1) {
              const desc = `${el.tagName.toLowerCase()}${
                el.className ? '.' + el.className.trim().split(/\s+/).join('.') : ''
              } [right=${Math.round(rect.right)}px, max=${innerWidth}px]`;
              overflowOffenders.push(desc);
            }
          }
        }
      }

      function channelLum(c: number): number {
        const norm = c / 255;
        return norm <= 0.03928 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
      }

      function relativeLum(r: number, g: number, b: number): number {
        return 0.2126 * channelLum(r) + 0.7152 * channelLum(g) + 0.0722 * channelLum(b);
      }

      function parseRgb(str: string): { r: number; g: number; b: number; a: number } | null {
        const m = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
        if (!m) return null;
        return {
          r: parseInt(m[1], 10),
          g: parseInt(m[2], 10),
          b: parseInt(m[3], 10),
          a: m[4] !== undefined ? parseFloat(m[4]) : 1,
        };
      }

      function getEffectiveBg(el: Element): { r: number; g: number; b: number } {
        let curr: Element | null = el;
        while (curr && curr !== document.documentElement) {
          const bg = window.getComputedStyle(curr).backgroundColor;
          const parsed = parseRgb(bg);
          if (parsed && parsed.a > 0.5) {
            return { r: parsed.r, g: parsed.g, b: parsed.b };
          }
          curr = curr.parentElement;
        }
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        return isDark ? { r: 9, g: 13, b: 22 } : { r: 248, g: 250, b: 252 };
      }

      const contrastOffenders: any[] = [];
      const textEls = document.querySelectorAll('p, td, span, button, a');
      for (const el of Array.from(textEls)) {
        const style = window.getComputedStyle(el);
        if (
          style.display === 'none' ||
          style.visibility === 'hidden' ||
          style.opacity === '0'
        ) {
          continue;
        }

        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;

        if (
          el.hasAttribute('disabled') ||
          (el as any).disabled ||
          el.closest('[disabled]')
        ) {
          continue;
        }

        const text = (el.textContent || '').trim();
        if (!text) continue;

        const hasDirectText = Array.from(el.childNodes).some(
          (n) => n.nodeType === Node.TEXT_NODE && (n.textContent || '').trim().length > 0
        );
        const isLeaf = el.children.length === 0;
        if (!hasDirectText && !isLeaf) continue;

        const fgParsed = parseRgb(style.color);
        if (!fgParsed) continue;
        const bgParsed = getEffectiveBg(el);

        const l1 = relativeLum(fgParsed.r, fgParsed.g, fgParsed.b);
        const l2 = relativeLum(bgParsed.r, bgParsed.g, bgParsed.b);
        const contrast = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);

        if (contrast < 4.49) {
          contrastOffenders.push({
            tag: el.tagName.toLowerCase(),
            text: text.slice(0, 30),
            color: style.color,
            bg: `rgb(${bgParsed.r}, ${bgParsed.g}, ${bgParsed.b})`,
            contrast: Math.round(contrast * 100) / 100,
          });
        }
      }

      return {
        horizontalScroll,
        scrollWidth,
        innerWidth,
        overflowOffenders: overflowOffenders.slice(0, 10),
        contrastOffenders: contrastOffenders.slice(0, 10),
      };
    }, vw);
  }

  async function captureAndAssert(pageName: string) {
    const viewports = [
      { width: 1280, height: 800 },
      { width: 375, height: 812 },
    ];
    const schemes: Array<'light' | 'dark'> = ['light'];

    for (const vp of viewports) {
      for (const scheme of schemes) {
        consoleErrors = [];

        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.emulateMedia({ colorScheme: scheme });
        await page.waitForTimeout(300);

        const screenshotFile = `${pageName}-${vp.width}-${scheme}.png`;
        const filepath = path.join(SCREENSHOTS_DIR, screenshotFile);
        await page.screenshot({ path: filepath, fullPage: true });

        const layout = await runLayoutChecks(page, vp.width);

        const summary: PageCheckSummary = {
          page: pageName,
          width: vp.width,
          scheme,
          noHorizontalScroll: !layout.horizontalScroll,
          noOverflow: layout.overflowOffenders.length === 0,
          contrastPass: layout.contrastOffenders.length === 0,
          consoleErrorsCount: consoleErrors.length,
          screenshotFile,
        };
        checkSummaries.push(summary);

        if (layout.horizontalScroll) {
          console.error(
            `[H-Scroll Error] ${pageName} (${vp.width}px, ${scheme}): scrollWidth=${layout.scrollWidth} > innerWidth=${layout.innerWidth}`
          );
        }
        if (layout.overflowOffenders.length > 0) {
          console.error(
            `[Overflow Error] ${pageName} (${vp.width}px, ${scheme}):`,
            layout.overflowOffenders
          );
        }
        if (layout.contrastOffenders.length > 0) {
          console.error(
            `[Contrast Error] ${pageName} (${vp.width}px, ${scheme}):`,
            layout.contrastOffenders
          );
        }
        if (consoleErrors.length > 0) {
          console.error(
            `[Console Errors] ${pageName} (${vp.width}px, ${scheme}):`,
            consoleErrors
          );
        }

        expect(
          layout.horizontalScroll,
          `Page ${pageName} has horizontal scroll at ${vp.width}px ${scheme}`
        ).toBe(false);

        expect(
          layout.overflowOffenders,
          `Page ${pageName} has overflowing elements at ${vp.width}px ${scheme}`
        ).toHaveLength(0);

        expect(
          layout.contrastOffenders,
          `Page ${pageName} has low contrast elements at ${vp.width}px ${scheme}`
        ).toHaveLength(0);

        expect(
          consoleErrors,
          `Page ${pageName} logged console errors at ${vp.width}px ${scheme}`
        ).toHaveLength(0);

        // Regression assertion: at 375 px every nav link's bounding box is fully inside the viewport
        if (vp.width === 375) {
          const navLinks = page.locator('.topnav .topnav__link');
          const navCount = await navLinks.count();
          expect(navCount).toBeGreaterThanOrEqual(5);
          for (let i = 0; i < navCount; i++) {
            const link = navLinks.nth(i);
            const box = await link.boundingBox();
            expect(box).toBeTruthy();
            if (box) {
              expect(
                box.x,
                `Nav link #${i} on ${pageName} (${scheme}) is outside viewport left (x=${box.x})`
              ).toBeGreaterThanOrEqual(0);
              expect(
                box.x + box.width,
                `Nav link #${i} on ${pageName} (${scheme}) is outside viewport right (right=${box.x + box.width})`
              ).toBeLessThanOrEqual(376);
            }
          }
        }
      }
    }
  }

  // 1. Marketplace (/)
  test('1. Directory (/)', async () => {
    await page.goto('/');
    await expect(page.locator('li[data-testid^="service-"]')).toHaveCount(16, { timeout: 20_000 });
    await captureAndAssert('directory');
  });

  test('2. Directory with the text-to-speech comparison open', async () => {
    await page.goto('/');
    await page.getByTestId('service-tts').locator('button').click();
    await expect(page.getByTestId('comparison').locator('tbody tr')).toHaveCount(4);
    await captureAndAssert('directory-tts');
  });

  test('3. Vendors index', async () => {
    await page.goto('/vendors');
    await expect(page.locator('[data-testid^="poster-"]')).toHaveCount(4, { timeout: 20_000 });
    await captureAndAssert('vendors');
  });

  for (const slug of ['nova-labs', 'blue-fern', 'quarry-compute', 'lumen-works']) {
    test(`4. Storefront ${slug}`, async () => {
      await page.goto(`/vendors/${slug}`);
      await expect(page.getByTestId('vendor-pass')).toBeVisible({ timeout: 20_000 });
      await captureAndAssert(`store-${slug}`);
    });
  }

  test('5. Service page before a call', async () => {
    await page.goto('/listing/tts-1');
    await expect(page.getByTestId('pay-run')).toBeVisible({ timeout: 20_000 });
    await captureAndAssert('service-tts-1-before');
  });

  test('6. Service page after a paid call', async () => {
    await page.goto('/listing/tts-1');
    await page.getByTestId('field-text').fill('hello screens spec synthesis');
    await page.getByTestId('pay-run').click();
    await expect(page.getByTestId('result-text')).toContainText('.wav', { timeout: 60_000 });
    const paid = page.getByTestId('paid-txid');
    await expect(paid).toContainText('ALGO');
    await expect(paid).not.toContainText(/\d 0,/); // the old bug rendered the asset id: "paid 0.02 0, tx"
    paidTxid = ((await paid.locator('a').getAttribute('href')) || '').replace('/explorer/tx/', '');
    const info = await lookupTransaction(paidTxid);
    confirmedRound = Number(info?.['confirmed-round'] || 0);
    await captureAndAssert('service-tts-1-after');
  });

  test('7. Wallet', async () => {
    await page.goto('/wallet');
    await expect(page.getByTestId('faucet-btn')).toBeVisible({ timeout: 20_000 });
    await captureAndAssert('wallet');
  });

  test('8. History', async () => {
    await page.goto('/history');
    await expect(page.getByTestId('history-row').first()).toBeVisible({ timeout: 20_000 });
    await captureAndAssert('history');
  });

  test('9. Explorer', async () => {
    await page.goto('/explorer');
    await expect(page.getByTestId('block-row').first()).toBeVisible({ timeout: 20_000 });
    await captureAndAssert('explorer');
  });

  test('10. Block', async () => {
    await page.goto(`/explorer/block/${confirmedRound}`);
    await expect(page.getByTestId('hash-ok')).toBeVisible({ timeout: 20_000 });
    await captureAndAssert('explorer-block');
  });

  // Every service has its own tool interface, shown in every vendor's identity: check all 64 listings.
  test('12. Every service page in every vendor identity', async () => {
    test.setTimeout(900_000)
    const listings: Array<{ id: string }> = await (await fetch('http://localhost:8800/api/listings')).json()
    const problems: string[] = []
    for (const { id } of listings) {
      for (const width of [1280, 375]) {
        consoleErrors = []
        await page.setViewportSize({ width, height: 900 })
        await page.goto(`/listing/${id}`)
        await expect(page.getByTestId('pay-run').first()).toBeVisible({ timeout: 20_000 })
        await page.waitForTimeout(300)
        const layout = await runLayoutChecks(page, width)
        const errs = consoleErrors.filter((e) => !/402/.test(e))
        if (layout.horizontalScroll) problems.push(`${id} @${width}: horizontal scroll ${layout.scrollWidth}px`)
        if (layout.overflowOffenders.length) problems.push(`${id} @${width}: overflow ${layout.overflowOffenders.slice(0, 3).join(', ')}`)
        if (layout.contrastOffenders.length)
          problems.push(`${id} @${width}: contrast ${layout.contrastOffenders.slice(0, 3).map((c) => `"${c.text}" ${c.contrast}`).join(', ')}`)
        if (errs.length) problems.push(`${id} @${width}: console ${errs.slice(0, 2).join(' | ')}`)
      }
      if (/-1$|-4$/.test(id)) await page.screenshot({ path: path.join(SCREENSHOTS_DIR, `tool-${id}-375.png`), fullPage: true })
    }
    if (problems.length) console.error('[Tool pages]\n' + problems.join('\n'))
    expect(problems, problems.join('\n')).toHaveLength(0)
  })

  test('11. Transaction receipt', async () => {
    await page.goto(`/explorer/tx/${paidTxid}`);
    await expect(page.locator('.receipt__amount')).toContainText('ALGO', { timeout: 20_000 });
    await captureAndAssert('explorer-tx');
  });
});
