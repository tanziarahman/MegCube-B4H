import { expect, test } from '@playwright/test';

test.describe('portal authentication and navigation', () => {
  test('rejects invalid credentials without leaving login', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('operator');
    await page.getByLabel('Password').fill('incorrect');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page.getByRole('alert')).toHaveText('Incorrect username or password.');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('submits valid credentials and navigates across portal routes', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('operator');
    await page.getByLabel('Password').fill('admin');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
    await page.getByRole('link', { name: 'People' }).click();
    await expect(page).toHaveURL(/\/people$/);
    await expect(page.getByRole('heading', { name: 'People' })).toBeVisible();
  });

  test('supports keyboard access to the user menu and sign out', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Username' }).fill('operator');
    await page.getByLabel('Password').fill('admin');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();

    const menuButton = page.getByRole('button', { name: /Admin/ });
    await menuButton.focus();
    await page.keyboard.press('Enter');
    await expect(menuButton).toHaveAttribute('aria-expanded', 'true');
    await page.keyboard.press('Escape');
    await expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    await page.keyboard.press('Enter');
    await page.getByRole('menuitem', { name: 'Sign out' }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});
