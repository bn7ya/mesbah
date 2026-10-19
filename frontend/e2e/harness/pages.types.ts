import type { BrowserContext, Page } from '@playwright/test';

export interface FreshPage {
  readonly context: BrowserContext;
  readonly page: Page;
  readonly problems: readonly string[];
}
