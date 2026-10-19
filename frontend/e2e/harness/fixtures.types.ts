import type { Page } from '@playwright/test';

import type { MesbahApi } from './api';
import type { Copy, UiLocale } from './copy.types';
import type { Stack } from './stack.types';
import type { Role, World } from './world.types';

export interface Fixtures {
  readonly uiLocale: UiLocale | null;
  readonly allowConsoleErrors: boolean;
  readonly locale: UiLocale;
  readonly t: Copy;
  readonly owner: MesbahApi;
  readonly as: (role: Role) => Promise<Page>;
  readonly shot: (name: string) => Promise<void>;
  readonly consoleGuard: undefined;
}

export interface WorkerFixtures {
  readonly stack: Stack;
  readonly world: World;
}
