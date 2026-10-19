import { join } from 'node:path';

import { defineConfig, devices, type ReporterDescription } from '@playwright/test';

import type { Fixtures } from './harness/fixtures.types';
import { PORT, RESULTS, readStack } from './harness/stack';
import { stateFile } from './harness/world';

const CI = Boolean(process.env['CI']);
const chromium = process.env['E2E_CHROMIUM'];
const desktop = devices['Desktop Chrome'];
const signedIn = { storageState: stateFile('owner') };
const journeys = /journeys\/[^/]+\.spec\.ts$/;
const reporters: ReporterDescription[] = [
  ['list'],
  ['html', { outputFolder: join(RESULTS, 'report'), open: 'never' }],
  ['junit', { outputFile: join(RESULTS, 'junit.xml') }],
];

export default defineConfig<Fixtures>({
  testDir: './journeys',
  outputDir: join(RESULTS, 'artifacts'),
  globalSetup: './global-setup.ts',
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: CI ? [...reporters, ['github']] : reporters,
  use: {
    baseURL: process.env['E2E_STACK'] ? readStack().base_url : `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ...(chromium ? { launchOptions: { executablePath: chromium } } : {}),
  },
  projects: [
    { name: 'setup', testMatch: /setup\.setup\.ts$/, use: { ...desktop, uiLocale: 'ar' } },
    {
      name: 'ltr',
      testMatch: journeys,
      dependencies: ['setup'],
      use: { ...desktop, locale: 'en-US', uiLocale: 'en', ...signedIn },
    },
    {
      name: 'rtl',
      testMatch: journeys,
      dependencies: ['setup'],
      use: { ...desktop, locale: 'ar', uiLocale: 'ar', ...signedIn },
    },
    {
      name: 'trains-ltr',
      testMatch: /journeys\/trains\/.+\.spec\.ts$/,
      dependencies: ['ltr', 'rtl'],
      workers: 1,
      use: { ...desktop, locale: 'en-US', uiLocale: 'en', ...signedIn },
    },
    {
      name: 'trains-rtl',
      testMatch: /journeys\/trains\/.+\.spec\.ts$/,
      dependencies: ['trains-ltr'],
      workers: 1,
      use: { ...desktop, locale: 'ar', uiLocale: 'ar', ...signedIn },
    },
  ],
});
