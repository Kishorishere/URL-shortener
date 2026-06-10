const { test, expect } = require('@playwright/test');
const { TEST_EMAIL, TEST_PASSWORD, UNVERIFIED_EMAIL, randomEmail, login, logout, verifyEmail } = require('../helpers');

test.describe('Authentication', () => {

  test.describe('Registration', () => {

    test('should register a new user and verify email via OTP', async ({ page }) => {
      const email = randomEmail();
      const username = `TestUser-${Date.now()}`;
      await page.goto('/register/', { waitUntil: 'load' });
      await page.fill('#username', username);
      await page.fill('#email', email);
      await page.fill('#password', 'NewPass123!');
      await page.fill('#confirm_password', 'NewPass123!');
      await page.click('button[type="submit"]');

      await page.waitForURL(/\/verify-email\//, { timeout: 10000 });
      await expect(page.locator('text=verification')).toBeVisible();

      await verifyEmail(page, email);
      await expect(page).toHaveURL(/\/dashboard\//);
      await expect(page.locator('text=My Links')).toBeVisible();
    });

    test('should show error on duplicate email', async ({ page }) => {
      await page.goto('/register/', { waitUntil: 'load' });
      await page.fill('#username', 'DupUser');
      await page.fill('#email', TEST_EMAIL);
      await page.fill('#password', 'NewPass123!');
      await page.fill('#confirm_password', 'NewPass123!');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=already exists')).toBeVisible({ timeout: 5000 });
    });

    test('should show error on password mismatch', async ({ page }) => {
      await page.goto('/register/', { waitUntil: 'load' });
      await page.fill('#username', 'MismatchUser');
      await page.fill('#email', randomEmail());
      await page.fill('#password', 'PassOne123!');
      await page.fill('#confirm_password', 'PassTwo456!');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=do not match')).toBeVisible({ timeout: 5000 });
    });

    test('should redirect to dashboard if already authenticated', async ({ page }) => {
      await login(page);
      await page.goto('/register/', { waitUntil: 'load' });
      await expect(page).toHaveURL(/\/dashboard\//);
    });

  });

  test.describe('Login', () => {

    test('should login with valid credentials', async ({ page }) => {
      await page.goto('/login/', { waitUntil: 'load' });
      await page.fill('#email', TEST_EMAIL);
      await page.fill('#password', TEST_PASSWORD);
      await page.click('button[type="submit"]');
      await page.waitForURL(/\/dashboard\//, { timeout: 10000 });

      await expect(page.locator(`text=${TEST_EMAIL}`)).toBeVisible();
    });

    test('should show error with wrong password', async ({ page }) => {
      await page.goto('/login/', { waitUntil: 'load' });
      await page.fill('#email', TEST_EMAIL);
      await page.fill('#password', 'WrongPassword999!');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=Invalid email or password')).toBeVisible({ timeout: 5000 });
    });

    test('should show verify email prompt for unverified user', async ({ page }) => {
      await page.goto('/login/', { waitUntil: 'load' });
      await page.fill('#email', UNVERIFIED_EMAIL);
      await page.fill('#password', TEST_PASSWORD);
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=verify your email')).toBeVisible();
    });

    test('should redirect to dashboard if already authenticated', async ({ page }) => {
      await login(page);
      await page.goto('/login/', { waitUntil: 'load' });
      await expect(page).toHaveURL(/\/dashboard\//);
    });

  });

  test.describe('Logout', () => {

    test('should logout successfully', async ({ page }) => {
      await login(page);
      await logout(page);
      await expect(page).toHaveURL(/\/login\//);
    });

  });

  test.describe('Forgot Password Flow', () => {

    test('should show sent message for existing email', async ({ page }) => {
      await page.goto('/forgot-password/', { waitUntil: 'load' });
      await page.fill('input[name="email"]', TEST_EMAIL);
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=Check your email')).toBeVisible({ timeout: 5000 });
    });

    test('should show sent message even for non-existing email', async ({ page }) => {
      await page.goto('/forgot-password/', { waitUntil: 'load' });
      await page.fill('input[name="email"]', 'nonexistent@example.com');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=Check your email')).toBeVisible({ timeout: 5000 });
    });

    test('should redirect to dashboard if already authenticated', async ({ page }) => {
      await login(page);
      await page.goto('/forgot-password/', { waitUntil: 'load' });
      await expect(page).toHaveURL(/\/dashboard\//);
    });

  });

  test.describe('Root Redirect', () => {

    test('should redirect authenticated user to dashboard', async ({ page }) => {
      await login(page);
      await page.goto('/');
      await expect(page).toHaveURL(/\/dashboard\//);
    });

    test('should redirect unauthenticated user to login', async ({ page }) => {
      await page.goto('/');
      await expect(page).toHaveURL(/\/login\//);
    });

  });

});
