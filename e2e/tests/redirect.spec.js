const { test, expect } = require('@playwright/test');

test.describe('Public Redirect', () => {

  test('should redirect to the original URL for an active short code', async ({ page }) => {
    const response = await page.request.get('/test1/', { maxRedirects: 0 });
    expect(response.status()).toBe(302);
    expect(response.headers()['location']).toContain('https://example.com/active');
  });

  test('should show 404 page for non-existent short code', async ({ page }) => {
    const response = await page.goto('/nonexistent123/');
    expect(response.status()).toBe(404);
    await expect(page.locator('text=404')).toBeVisible();
  });

  test('should show 410 expired page for expired link', async ({ page }) => {
    const response = await page.goto('/exp1/');
    expect(response.status()).toBe(410);
    await expect(page.locator('text=expired')).toBeVisible();
  });

  test.describe('Password Protected Links', () => {

    test('should show password gate for protected link', async ({ page }) => {
      await page.goto('/pwd1/');
      await expect(page.locator('h1:has-text("Password Required")')).toBeVisible();
    });

    test('should unlock with correct password and redirect', async ({ page }) => {
      await page.goto('/pwd1/', { waitUntil: 'load' });
      await page.fill('input[type="password"]', 'secret123');
      await page.click('button[type="submit"]');

      await page.waitForURL((url) => {
        return url.toString().includes('example.com') || !url.toString().includes('/password/');
      }, { timeout: 10000 });
    });

    test('should show error with wrong password', async ({ page }) => {
      await page.goto('/pwd1/', { waitUntil: 'load' });
      await page.fill('input[type="password"]', 'wrongpassword');
      await page.click('button[type="submit"]');

      await expect(page.locator('text=Incorrect password')).toBeVisible();
    });

  });

  test.describe('Preview Links', () => {

    test('should show preview page for links with show_preview enabled', async ({ page }) => {
      await page.goto('/prev1/');
      await expect(page.locator('text=You are being redirected')).toBeVisible();
      await expect(page.locator('text=https://example.com/preview')).toBeVisible();
      await expect(page.locator('a:has-text("Continue")')).toBeVisible();
    });

    test('should have continue link that goes to original URL', async ({ page }) => {
      await page.goto('/prev1/');
      const continueLink = page.locator('a:has-text("Continue")');
      const href = await continueLink.getAttribute('href');
      expect(href).toBe('https://example.com/preview');
    });

  });

});
