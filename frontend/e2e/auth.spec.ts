import { test, expect, type Page } from '@playwright/test';

/*
 * FaceSnap E2E — no webcam, no Firebase credentials.
 *
 * Exercises what can be exercised without signing in:
 *   * the app shell loads and hydrates past the auth loading state,
 *   * the public navigation renders,
 *   * registration requires sign-in,
 *   * auth-gated routes require sign-in.
 *
 * Google sign-in, real camera/liveness verification, and attendance end-to-end
 * are manual tests (see docs/testing.md § Manual checklist). A signed-in
 * backend-outage check is not automatable here without Firebase credentials.
 */

test.describe('FaceSnap frontend', () => {
  // Wait until Firebase auth has resolved (loading spinner gone).
  async function waitForAppReady(page: Page) {
    await expect(page.locator('text=Loading...')).not.toBeVisible({ timeout: 40000 });
  }

  test('app shell loads and shows the public navigation', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
    const nav = page.getByRole('navigation');
    await expect(nav.getByRole('link', { name: 'Home' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'About Us' })).toBeVisible();
    await expect(nav.getByRole('link', { name: 'Contact' })).toBeVisible();
    // Signed out: sign-in button is the primary call to action.
    await expect(page.getByRole('button', { name: /Sign In/i })).toBeVisible();
  });

  test('register page requires sign-in when unauthenticated', async ({ page }) => {
    await page.goto('/register');
    await waitForAppReady(page);
    await expect(page.getByRole('heading', { name: /Authentication Required/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Sign In to Continue/i })).toBeVisible();
  });

  test('student, attendance, classroom and cctv require sign-in when unauthenticated', async ({ page }) => {
    for (const route of ['/student', '/attendance', '/classroom', '/cctv']) {
      await page.goto(route);
      await waitForAppReady(page);
      await expect(
        page.locator('body').filter({ hasText: /Authentication Required|Sign In/i })
      ).toBeVisible();
    }
  });
});
