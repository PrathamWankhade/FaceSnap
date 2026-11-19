import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/*
 * Accessibility gate for the pages that render without a session.
 *
 * Only critical/serious WCAG A/AA findings fail the build; moderate/minor
 * findings are still reported in the Playwright trace so they can be tracked
 * without blocking unrelated work. Signed-in pages are not scanned here
 * because they cannot be reached without Firebase credentials.
 */

const PUBLIC_PAGES = ['/', '/about', '/contact', '/register', '/analytics'];

/**
 * Framer-motion fades content in from opacity 0. axe-core blends a partially
 * transparent text colour with the background, so scanning mid-animation
 * reports contrast failures that do not exist once the page has settled.
 *
 * `whileInView` cards only animate once scrolled into view, so walk the page
 * first and then wait for every in-viewport animated element to reach opacity 1.
 */
async function waitForAnimations(page: Page) {
  await page.evaluate(async () => {
    const step = Math.max(200, Math.floor(window.innerHeight * 0.8));
    for (let y = 0; y <= document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 80));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForFunction(
    () =>
      Array.from(document.querySelectorAll<HTMLElement>('[style*="opacity"]')).every((element) => {
        const rect = element.getBoundingClientRect();
        const inViewport = rect.bottom > 0 && rect.top < window.innerHeight;
        return !inViewport || Number.parseFloat(getComputedStyle(element).opacity) >= 0.999;
      }),
    undefined,
    { timeout: 10000 },
  );
}

for (const path of PUBLIC_PAGES) {
  test(`no critical or serious axe violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('text=Loading...')).toHaveCount(0, { timeout: 40000 });
    await waitForAnimations(page);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const blocking = results.violations.filter(
      (violation) => violation.impact === 'critical' || violation.impact === 'serious',
    );

    expect(
      blocking.map((violation) => ({
        rule: `${violation.id} (${violation.impact})`,
        help: violation.description,
        nodes: violation.nodes.map((node) => node.target.join(' ')),
      })),
    ).toEqual([]);
  });
}
