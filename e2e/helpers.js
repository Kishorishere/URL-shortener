const { expect } = require('@playwright/test');

const TEST_EMAIL = 'e2e-verified@example.com';
const TEST_PASSWORD = 'TestPass123!';
const UNVERIFIED_EMAIL = 'e2e-unverified@example.com';

function randomEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
}

async function login(page, email = TEST_EMAIL, password = TEST_PASSWORD) {
  await page.goto('/login/', { waitUntil: 'load' });
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard\//, { timeout: 10000 });
}

async function logout(page) {
  const logoutBtn = page.locator('button:has-text("Logout")');
  if (await logoutBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await logoutBtn.click();
    await page.waitForURL(/\/login\//, { timeout: 10000 });
  }
}

async function getOtp(email) {
  const response = await fetch(`http://localhost:8000/debug/otp/?email=${encodeURIComponent(email)}`);
  const data = await response.json();
  return data.otp;
}

async function verifyEmail(page, email) {
  await page.goto('/verify-email/', { waitUntil: 'load' });
  const otp = await getOtp(email);
  if (!otp) throw new Error(`No OTP found for ${email}`);
  await page.fill('input[name="otp"]', otp);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard\//, { timeout: 10000 });
}

async function createLink(page, originalUrl, extraFields = {}) {
  await page.goto('/dashboard/create/', { waitUntil: 'load' });
  await page.fill('input[name="original_url"]', originalUrl);
  if (extraFields.title) await page.fill('input[name="title"]', extraFields.title);
  if (extraFields.custom_slug) await page.fill('input[name="custom_slug"]', extraFields.custom_slug);
  if (extraFields.password) await page.fill('input[name="password"]', extraFields.password);
  if (extraFields.show_preview) await page.check('input[name="show_preview"]');
  if (extraFields.expires_at) await page.fill('input[name="expires_at"]', extraFields.expires_at);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard\//, { timeout: 10000 });
}

async function getCsrfToken(page) {
  const csrf = await page.locator('input[name="csrfmiddlewaretoken"]').first().getAttribute('value');
  return csrf;
}

module.exports = {
  TEST_EMAIL,
  TEST_PASSWORD,
  UNVERIFIED_EMAIL,
  randomEmail,
  login,
  logout,
  getOtp,
  verifyEmail,
  createLink,
  getCsrfToken,
};
