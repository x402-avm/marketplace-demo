import { Page, expect } from '@playwright/test';

/**
 * Connects the given mnemonic via the dev Mnemonic wallet provider on /wallet.
 */
export async function connectMnemonic(page: Page, mnemonic: string) {
  // Handle the prompt dialog for the 25-word mnemonic
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(mnemonic);
    } else {
      await dialog.accept();
    }
  });

  // Navigate to /wallet if not on it
  if (!page.url().includes('/wallet')) {
    await page.goto('/wallet');
  }

  const connectBtn = page.locator('[data-testid="connect-mnemonic"]');
  await expect(connectBtn).toBeVisible({ timeout: 10_000 });
  await connectBtn.click();

  // Verify connected wallet is active
  await expect(page.getByTestId('faucet-btn')).toBeVisible({ timeout: 15_000 });
}
