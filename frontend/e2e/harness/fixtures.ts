import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { test as base, expect, type BrowserContext, type Page } from '@playwright/test';

import { MesbahApi } from './api';
import { label } from './copy';
import type { UiLocale } from './copy.types';
import type { Fixtures, WorkerFixtures } from './fixtures.types';
import { RESULTS, readStack } from './stack';
import { readWorld, stateFile } from './world';

const IGNORED_CONSOLE: readonly RegExp[] = [/^Failed to load resource/];

export async function startIn(page: Page, locale: UiLocale | null): Promise<void> {
  if (locale) {
    await page.addInitScript((chosen) => {
      if (!localStorage.getItem('locale')) {
        localStorage.setItem('locale', chosen);
      }
    }, locale);
  }
}

export function recordErrors(page: Page): readonly string[] {
  const problems: string[] = [];
  page.on('pageerror', (error) => problems.push(`page error: ${error.message}`));
  page.on('console', (message) => {
    const said = message.text();
    if (message.type() === 'error' && !IGNORED_CONSOLE.some((ignored) => ignored.test(said))) {
      problems.push(`console error: ${said}`);
    }
  });
  return problems;
}

// The document, and <main> with every box around it, since the shell scrolls inside its own box.
export async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() => {
    const boxes: Element[] = [document.documentElement];
    for (let box = document.getElementById('main'); box; box = box.parentElement) {
      boxes.push(box);
    }
    return Math.max(...boxes.map((box) => Math.max(box.scrollWidth - box.clientWidth, Math.abs(box.scrollLeft))));
  });
}

// The menu sits beside the page on a wide screen; only on a narrow one does it slide over it.
async function underTheMenu(page: Page): Promise<number> {
  return page.evaluate(() => {
    const menu = document.querySelector('mat-sidenav.mat-drawer-side.mat-drawer-opened');
    const main = document.getElementById('main');
    if (!menu || !main) {
      return 0;
    }
    const [beside, content] = [menu.getBoundingClientRect(), main.getBoundingClientRect()];
    return Math.max(0, Math.min(beside.right, content.right) - Math.max(beside.left, content.left));
  });
}

function fileName(text: string): string {
  return text.replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '').toLowerCase();
}

export const test = base.extend<Fixtures, WorkerFixtures>({
  uiLocale: ['en', { option: true }],
  allowConsoleErrors: [false, { option: true }],
  // eslint-disable-next-line no-empty-pattern -- Playwright reads a fixture's dependencies from this pattern
  stack: [async ({}, use) => use(readStack()), { scope: 'worker' }],
  // eslint-disable-next-line no-empty-pattern -- as above
  world: [async ({}, use) => use(readWorld()), { scope: 'worker' }],
  locale: async ({ uiLocale }, use) => use(uiLocale ?? 'ar'),
  page: async ({ page, uiLocale }, use) => {
    await startIn(page, uiLocale);
    await use(page);
  },
  t: async ({ locale }, use) => use((bundle, key, values) => label(bundle, locale, key, values)),
  owner: async ({ stack, world }, use) => {
    const api = await MesbahApi.signIn(stack.base_url, world.users.owner, world.password);
    await use(api);
    await api.dispose();
  },
  as: async ({ browser, uiLocale, baseURL }, use) => {
    const opened: BrowserContext[] = [];
    await use(async (role) => {
      const context = await browser.newContext({ storageState: stateFile(role), baseURL });
      opened.push(context);
      const page = await context.newPage();
      await startIn(page, uiLocale);
      return page;
    });
    for (const context of opened) {
      await context.close();
    }
  },
  shot: async ({ page }, use, testInfo) => {
    let taken = 0;
    const folder = join(RESULTS, 'screens', testInfo.project.name, fileName(testInfo.titlePath.slice(1).join(' ')));
    await use(async (name, shown = page) => {
      taken += 1;
      mkdirSync(folder, { recursive: true });
      const path = join(folder, `${String(taken).padStart(2, '0')}-${fileName(name)}.png`);
      expect(await horizontalOverflow(shown), `pixels "${name}" scrolls sideways`).toBeLessThanOrEqual(1);
      expect(await underTheMenu(shown), `pixels of "${name}" under the side menu`).toBeLessThanOrEqual(1);
      // A dialog's backdrop covers the window, not the page below it, so the window is what is shot.
      const overlaid = (await shown.locator('.cdk-overlay-backdrop-showing').count()) > 0;
      await shown.screenshot({ path, fullPage: !overlaid, animations: 'disabled', caret: 'hide' });
      await testInfo.attach(name, { path, contentType: 'image/png' });
    });
  },
  consoleGuard: [
    async ({ page, allowConsoleErrors }, use) => {
      const problems = recordErrors(page);
      await use(undefined);
      if (!allowConsoleErrors) {
        expect(problems, 'the page logged errors').toEqual([]);
      }
    },
    { auto: true },
  ],
});

export { expect };
