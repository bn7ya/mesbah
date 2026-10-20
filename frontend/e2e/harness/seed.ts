import { field, isJson, rows, type MesbahApi } from './api';
import type { Json } from './api.types';

export const PASSWORD = 'e2e-journeys-password-7';

export const CHAT_ROWS: readonly Json[] = Array.from({ length: 12 }, (_, index) => ({
  messages: [
    { role: 'user', content: `Question ${index + 1}?` },
    { role: 'assistant', content: `Answer ${index + 1}.`, thinking: `Think about ${index + 1}.` },
  ],
}));

export function jsonl(lines: readonly Json[]): Buffer {
  return Buffer.from(`${lines.map((line) => JSON.stringify(line)).join('\n')}\n`);
}

export async function addMember(api: MesbahApi, username: string, role: string): Promise<void> {
  await api.post('/api/members/', { username, password: PASSWORD, role });
}

export async function uploadDataset(api: MesbahApi, name: string): Promise<string> {
  const created = await api.upload(
    '/api/datasets/upload/',
    { name: 'chat.jsonl', mimeType: 'application/x-ndjson', buffer: jsonl(CHAT_ROWS) },
    { name },
  );
  const id = field(created, 'id');
  await api.until(`/api/datasets/${id}/`, (dataset) => dataset['status'] === 'ready');
  return id;
}

export async function finished(api: MesbahApi, run: string): Promise<Json> {
  const done = await api.until(`/api/training/${run}/`, (body) =>
    ['completed', 'failed', 'cancelled'].includes(String(body['status'])),
  );
  if (done['status'] !== 'completed') {
    throw new Error(`run ${run} ended ${String(done['status'])}: ${String(done['error_code'])}`);
  }
  return done;
}

export async function pretrainBase(api: MesbahApi, dataset: string, name: string): Promise<string> {
  const presets = rows(await api.get('/api/architect/presets/'), 'presets');
  const smallest = presets[0];
  if (!smallest || !isJson(smallest['design'])) {
    throw new Error('the Architect offers no preset');
  }
  const draft = await api.post('/api/architect/drafts/', {
    name,
    design: smallest['design'],
    tokenizer: 'e2e/tokenizer',
    seq_len: 128,
    batch: 2,
  });
  const started = await api.post(`/api/architect/drafts/${field(draft, 'id')}/train/`, {
    name,
    datasets: [{ id: dataset }],
  });
  await finished(api, field(started, 'run'));
  const models = rows(await api.get('/api/models/'));
  const made = models.find((model) => String(model['repo_id']).startsWith('local/'));
  if (!made) {
    throw new Error('pretraining left no model in the library');
  }
  return field(made, 'id');
}

export async function createProject(api: MesbahApi, name: string, baseModel: string): Promise<string> {
  return field(await api.post('/api/projects/', { name, base_model: baseModel }), 'id');
}

export async function trainVersion(
  api: MesbahApi,
  project: string,
  dataset: string,
  startsFrom: string | null = null,
): Promise<string> {
  const run = await api.post('/api/training/', {
    project,
    datasets: [{ id: dataset }],
    starts_from: startsFrom,
    use_corrections: false,
  });
  const done = await finished(api, field(run, 'id'));
  const version = done['version'];
  if (typeof version === 'string') {
    return version;
  }
  if (isJson(version)) {
    return field(version, 'id');
  }
  throw new Error(`run ${field(run, 'id')} names no version`);
}
