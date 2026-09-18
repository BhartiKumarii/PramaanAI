import { test, expect } from '@playwright/test';

test.describe('PramaanAI Web App', () => {
  test('home page loads', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/PramaanAI/);
  });

  test('login page accessible', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input[id="username"]')).toBeVisible();
    await expect(page.locator('input[id="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('login with valid credentials (supervisor)', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="username"]', 'supervisor1');
    await page.fill('input[id="password"]', 'BorderShield123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/.*console/);
  });

  test('dashboard accessible after login (supervisor)', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="username"]', 'supervisor1');
    await page.fill('input[id="password"]', 'BorderShield123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*console/);
    await expect(page.locator('h1:has-text("Overview")')).toBeVisible();
  });

  test('navigation to cases page (supervisor)', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="username"]', 'supervisor1');
    await page.fill('input[id="password"]', 'BorderShield123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*console/);
    await page.click('text=Cases');
    await expect(page).toHaveURL(/.*cases/);
  });

  test('navigation to alerts page (supervisor)', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="username"]', 'supervisor1');
    await page.fill('input[id="password"]', 'BorderShield123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*console/);
    await page.click('text=Alerts & Review');
    await expect(page).toHaveURL(/.*alerts/);
  });

  test('navigation to person search (supervisor)', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="username"]', 'supervisor1');
    await page.fill('input[id="password"]', 'BorderShield123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*console/);
    await page.click('text=Person Search');
    await expect(page).toHaveURL(/.*person-search/);
  });

  test('login with admin credentials (officer1)', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="username"]', 'officer1');
    await page.fill('input[id="password"]', 'BorderShield123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/.*console/);
  });

  test('navigation to admin users (admin)', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[id="username"]', 'officer1');
    await page.fill('input[id="password"]', 'BorderShield123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*console/);
    await page.click('text=Users');
    await expect(page).toHaveURL(/.*admin\/users/);
  });
});