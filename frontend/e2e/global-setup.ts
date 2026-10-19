import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { join } from 'node:path';

import { BACKEND, PORT, RESULTS } from './harness/stack';

function stack(...argv: string[]): void {
  execFileSync(process.env['E2E_PYTHON'] ?? 'python3', ['-m', 'tools.release.stack', ...argv], {
    cwd: BACKEND,
    stdio: 'inherit',
  });
}

export default function globalSetup(): () => void {
  if (process.env['E2E_STACK']) {
    return () => undefined;
  }
  rmSync(RESULTS, { recursive: true, force: true });
  const python = process.env['E2E_PYTHON'] ?? 'python3';
  const started = [
    'start',
    '--data',
    join(RESULTS, 'data'),
    '--out',
    join(RESULTS, 'stack'),
    '--port',
    String(PORT),
    '--engine-port',
    String(PORT + 1),
    '--engine-python',
    python,
  ];
  const mesbah = process.env['E2E_MESBAH'];
  const database = process.env['E2E_DATABASE_URL'];
  stack(...started, ...(mesbah ? ['--mesbah', mesbah] : []), ...(database ? ['--database-url', database] : []));
  return () => stack('stop', '--out', join(RESULTS, 'stack'));
}
