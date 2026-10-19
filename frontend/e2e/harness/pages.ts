import { expect, type Browser, type Locator, type Page } from '@playwright/test';

import { isJson } from './api';
import type { Upload } from './api.types';
import type { UiLocale } from './copy.types';
import { recordErrors, startIn } from './fixtures';
import type { FreshPage } from './pages.types';

// A press that lands while the list is still settling can focus the trigger without opening it.
export async function choose(trigger: Locator, item: Locator): Promise<void> {
  await expect(async () => {
    if (!(await item.isVisible())) {
      await trigger.click();
    }
    await expect(item).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 15_000 });
  await item.click();
}

export async function pickFile(page: Page, button: Locator, file: Upload): Promise<void> {
  const chooser = page.waitForEvent('filechooser');
  await button.click();
  await (await chooser).setFiles(file);
}

export async function signedOut(browser: Browser, baseUrl: string, locale: UiLocale): Promise<FreshPage> {
  const context = await browser.newContext({ baseURL: baseUrl, storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  await startIn(page, locale);
  return { context, page, problems: recordErrors(page) };
}

export async function settled(page: Page): Promise<void> {
  await expect(page.locator('main [aria-busy="true"]')).toHaveCount(0);
  await expect(page.locator('main mat-progress-bar[mode="indeterminate"]')).toHaveCount(0);
}

export async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

export async function estimated(page: Page, layers: number): Promise<void> {
  await page.waitForResponse((response) => {
    if (!response.url().endsWith('/api/architect/estimate/')) {
      return false;
    }
    const sent: unknown = response.request().postDataJSON();
    const design = isJson(sent) ? sent['design'] : null;
    return isJson(design) && design['layers'] === layers;
  });
  await settled(page);
}
