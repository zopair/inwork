const { test, expect } = require('@playwright/test');

test('InWork boots and shows the Arabic onboarding screen', async ({ page }) => {
  await page.goto('/index.html');
  await expect(page).toHaveTitle(/InWork/);
  await expect(page.locator('#app')).not.toBeEmpty();
  await expect(page.getByText('InWork', { exact: true }).first()).toBeVisible();
});

test('InWork onboarding can enter the main experience', async ({ page }) => {
  await page.goto('/index.html');
  const buttons = page.locator('button');
  await expect(buttons.first()).toBeVisible();
  await buttons.first().click();
  await expect(page.locator('#app')).not.toBeEmpty();
});
