const { test, expect } = require('@playwright/test');
const { login, TEST_EMAIL, TEST_PASSWORD } = require('../helpers');

const API_BASE = 'http://localhost:8000/api/v1';

test.describe('API', () => {

  test.describe('Links API', () => {

    test('should get 401 without authentication', async ({ page }) => {
      const response = await page.request.get(`${API_BASE}/links/`);
      expect(response.status()).toBe(401);
    });

    test('should list links with cookie auth', async ({ page }) => {
      await login(page);
      const response = await page.request.get(`${API_BASE}/links/`, {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(Array.isArray(data.results || data)).toBe(true);
    });

    test('should create a link via API', async ({ page }) => {
      await login(page);
      const response = await page.request.post(`${API_BASE}/links/`, {
        headers: { 'Content-Type': 'application/json' },
        data: {
          original_url: 'https://example.com/api-created',
          title: 'API Created Link',
        },
      });
      expect(response.status()).toBe(201);
      const data = await response.json();
      expect(data.original_url).toBe('https://example.com/api-created');
      expect(data.short_code).toBeDefined();
    });

    test('should update a link via API', async ({ page }) => {
      await login(page);

      const listResp = await page.request.get(`${API_BASE}/links/`);
      const listData = await listResp.json();
      const links = listData.results || listData;
      if (links.length === 0) return;
      const firstId = links[0].id;

      const response = await page.request.patch(`${API_BASE}/links/${firstId}/`, {
        headers: { 'Content-Type': 'application/json' },
        data: { title: 'API Updated Title' },
      });
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data.title).toBe('API Updated Title');
    });

    test('should soft-delete a link via API', async ({ page }) => {
      await login(page);

      const listResp = await page.request.get(`${API_BASE}/links/`);
      const listData = await listResp.json();
      const links = listData.results || listData;
      if (links.length === 0) return;

      const toDelete = links.find(l => !l.is_deleted);
      if (!toDelete) return;

      const response = await page.request.post(`${API_BASE}/links/${toDelete.id}/soft_delete/`);
      expect(response.status()).toBe(204);
    });

  });

  test.describe('Tags API', () => {

    test('should list tags', async ({ page }) => {
      await login(page);
      const response = await page.request.get(`${API_BASE}/tags/`);
      expect(response.status()).toBe(200);
    });

    test('should create a tag', async ({ page }) => {
      await login(page);
      const tagName = `tag-${Date.now()}`;
      const response = await page.request.post(`${API_BASE}/tags/`, {
        headers: { 'Content-Type': 'application/json' },
        data: { name: tagName, color: '#ff0000' },
      });
      expect(response.status()).toBe(201);
      const data = await response.json();
      expect(data.name).toBe(tagName);
    });

  });

  test.describe('Domains API', () => {

    test('should list domains', async ({ page }) => {
      await login(page);
      const response = await page.request.get(`${API_BASE}/domains/`);
      expect(response.status()).toBe(200);
    });

  });

  test.describe('Bulk API', () => {

    test('should create links via bulk API', async ({ page }) => {
      await login(page);
      const csvContent = 'url\nhttps://example.com/bulk-api-1\nhttps://example.com/bulk-api-2\n';
      const buffer = Buffer.from(csvContent, 'utf-8');

      const response = await page.request.post(`${API_BASE}/bulk/`, {
        multipart: {
          file: {
            name: 'bulk.csv',
            mimeType: 'text/csv',
            buffer,
          },
        },
      });

      expect(response.ok()).toBeTruthy();
    });

  });

});
