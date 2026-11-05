const { test, expect } = require('@playwright/test');

async function boot(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/index.html');
  await expect(page.locator('#view')).toBeVisible();
  if (errors.length) throw new Error('InWork browser runtime error: ' + errors.join(' | '));
}

test('InWork opens the Arabic service marketplace with no mock listings', async ({ page }) => {
  await boot(page);
  await expect(page).toHaveTitle(/InWork/);
  await expect(page.getByRole('heading', { name: /خدمة محتاجها/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'أحتاج خدمة' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'أقدم خدمة' })).toBeVisible();
  await expect(page.locator('#apiBase')).toBeVisible();
});

test('requester entry opens real account registration fields', async ({ page }) => {
  await boot(page);
  await page.getByRole('button', { name: 'أحتاج خدمة' }).click();
  await expect(page.locator('#email')).toBeVisible();
  await expect(page.locator('#displayName')).toBeVisible();
  await expect(page.locator('#password')).toBeVisible();
  await expect(page.locator('#role')).toHaveValue('requester');
});
