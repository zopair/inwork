const { test, expect } = require('@playwright/test');

async function boot(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/index.html');
  await page.waitForTimeout(250);
  if (errors.length) throw new Error(`InWork browser runtime error: ${errors.join(' | ')}`);
}

test('InWork boots and shows the Arabic onboarding screen', async ({ page }) => {
  await boot(page);
  await expect(page).toHaveTitle(/InWork/);
  await expect(page.locator('#app')).not.toBeEmpty();
  await expect(page.getByText('InWork', { exact: true }).first()).toBeVisible();
});

test('InWork onboarding can enter the main experience', async ({ page }) => {
  await boot(page);
  const buttons = page.locator('button');
  await expect(buttons.first()).toBeVisible();
  await buttons.first().click();
  await expect(page.locator('#app')).not.toBeEmpty();
});
