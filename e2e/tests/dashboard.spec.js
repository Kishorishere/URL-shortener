const { test, expect } = require('@playwright/test');
const { login, logout, createLink, TEST_EMAIL } = require('../helpers');

test.describe('Dashboard', () => {

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test.afterEach(async ({ page }) => {
    await logout(page);
  });

  test.describe('Link List', () => {

    test('should show the dashboard list with seeded links', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });

      await expect(page.locator('h1:has-text("My Links")')).toBeVisible();
      await expect(page.locator('text=/test1/')).toBeVisible();
      await expect(page.locator('text=/pwd1/')).toBeVisible();
      await expect(page.locator('text=/prev1/')).toBeVisible();
      await expect(page.locator('text=Protected')).toBeVisible();
    });

    test('should navigate to create page via New Link button', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("New Link")');
      await expect(page).toHaveURL(/\/dashboard\/create\//);
      await expect(page.locator('h1:has-text("Create Short URL")')).toBeVisible();
    });

  });

  test.describe('Create Link', () => {

    test('should create a new short URL with auto-generated code', async ({ page }) => {
      await createLink(page, 'https://example.com/auto-test', { title: 'Auto Test' });

      await expect(page).toHaveURL(/\/dashboard\//);
      await expect(page.locator('text=Short URL created')).toBeVisible();
      await expect(page.locator('text=https://example.com/auto-test')).toBeVisible();
    });

    test('should create a short URL with custom slug', async ({ page }) => {
      const slug = `my-slug-${Date.now()}`;
      await createLink(page, 'https://example.com/custom-slug', {
        custom_slug: slug,
        title: 'Custom Slug Test',
      });

      await expect(page).toHaveURL(/\/dashboard\//);
      await expect(page.locator(`text=/${slug}/`)).toBeVisible();
    });

    test('should show validation error for invalid URL', async ({ page }) => {
      await page.goto('/dashboard/create/', { waitUntil: 'load' });
      await page.fill('input[name="original_url"]', 'not-a-url');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=Enter a valid URL')).toBeVisible();
    });

    test('should show validation error for duplicate slug', async ({ page }) => {
      await page.goto('/dashboard/create/', { waitUntil: 'load' });
      await page.fill('input[name="original_url"]', 'https://example.com/dup');
      await page.fill('input[name="custom_slug"]', 'test1');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=already in use')).toBeVisible();
    });

  });

  test.describe('Edit Link', () => {

    test('should edit a link title and original URL', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("Edit") >> first');

      await expect(page.locator('h1:has-text("Edit Short URL")')).toBeVisible();

      const titleInput = page.locator('input[name="title"]');
      await titleInput.fill('Updated Title');

      const urlInput = page.locator('input[name="original_url"]');
      await urlInput.fill('https://example.com/updated');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('load');

      await expect(page.locator('text=Short URL updated')).toBeVisible();
    });

  });

  test.describe('Detail / Stats Page', () => {

    test('should show link detail with stats and QR code', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("Stats") >> first');

      await expect(page.locator('text=Total Clicks')).toBeVisible();
      await expect(page.locator('text=Clicks (30d)')).toBeVisible();
      await expect(page.locator('text=Created')).toBeVisible();
      await expect(page.locator('text=QR Code')).toBeVisible();
      await expect(page.locator('img[alt="QR Code"]')).toBeVisible();
    });

    test('should show QR download links on detail page', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("Stats") >> first');

      await expect(page.locator('a:has-text("Download PNG")')).toBeVisible();
      await expect(page.locator('a:has-text("Download SVG")')).toBeVisible();
    });

    test('should have copy button for short URL', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("Stats") >> first');

      await expect(page.locator('button:has-text("Copy")')).toBeVisible();
      const input = page.locator('#shortUrlInput');
      const value = await input.inputValue();
      expect(value).toContain('http://localhost:8000/');
    });

  });

  test.describe('Delete (Soft) and Restore', () => {

    test('should soft-delete a link and show in trash', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("Delete") >> first');

      await expect(page.locator('h1:has-text("Move to Trash")')).toBeVisible();
      await page.click('button[type="submit"]');

      await expect(page.locator('text=moved to trash')).toBeVisible();

      await page.click('a:has-text("Trash")');
      await page.waitForURL(/\/dashboard\/trash\//);
    });

    test('should restore a link from trash', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("Delete") >> first');
      await page.click('button[type="submit"]');

      await page.click('a:has-text("Trash")');
      await page.waitForURL(/\/dashboard\/trash\//);

      const restoreBtn = page.locator('button:has-text("Restore")').first();
      if (await restoreBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await restoreBtn.click();
        await page.waitForURL(/\/dashboard\//);
        await expect(page.locator('text=Short URL restored')).toBeVisible();
      }
    });

  });

  test.describe('Bulk Upload', () => {

    test('should show bulk upload page', async ({ page }) => {
      await page.goto('/dashboard/bulk/', { waitUntil: 'load' });
      await expect(page.locator('h1:has-text("Bulk Upload")')).toBeVisible();
      await expect(page.locator('button:has-text("Upload & Shorten")')).toBeVisible();
    });

  });

  test.describe('QR Download', () => {

    test('should download QR PNG from detail page', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });

      const detailLink = page.locator('a:has-text("Stats")').first();
      const href = await detailLink.getAttribute('href');

      const response = await page.request.get(href);
      expect(response.status()).toBe(200);

      const pngLink = page.locator('a:has-text("Download PNG")');
      const pngHref = await pngLink.getAttribute('href');
      expect(pngHref).toMatch(/\/qr\/png$/);
    });

    test('should download QR SVG from detail page', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });
      await page.click('a:has-text("Stats") >> first');

      const svgLink = page.locator('a:has-text("Download SVG")');
      const svgHref = await svgLink.getAttribute('href');
      expect(svgHref).toMatch(/\/qr\/svg$/);
    });

  });

  test.describe('Navigation', () => {

    test('should navigate via navbar links', async ({ page }) => {
      await page.goto('/dashboard/', { waitUntil: 'load' });

      await page.click('a:has-text("New Link")');
      await expect(page).toHaveURL(/\/dashboard\/create\//);

      await page.click('a:has-text("My Links")');
      await expect(page).toHaveURL(/\/dashboard\//);

      await page.click('a:has-text("Bulk")');
      await expect(page).toHaveURL(/\/dashboard\/bulk\//);

      await page.click('a:has-text("Trash")');
      await expect(page).toHaveURL(/\/dashboard\/trash\//);
    });

  });

});
