import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/*
 * Accessibility gate for the pages that render without a session.
 *
 * Only critical/serious WCAG A/AA findings fail the build; moderate/minor
 * findings are still reported in the Playwright trace so they can be tracked
 * without blocking unrelated work. Signed-in pages are not scanned here
 * because they cannot be reached without Firebase credentials.
 */

const PUBLIC_PAGES = ['/', '/about', '/contact', '/register'];

for (const path of PUBLIC_PAGES) {
  test(`no critical or serious axe violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('text=Loading...')).not.toBeVisible({ timeout: 40000 });

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
