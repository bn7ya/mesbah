import { field, rows, type MesbahApi } from './api';
import type { Json } from './api.types';
import { text } from './copy';
import type { UiLocale } from './copy.types';
import type { VersionRow } from './versions.types';

const ROOT_NUMBER = 0;
const SEEDED_ROOT_NAME = 'base';

function toVersion(row: Json): VersionRow {
  const parent = row['parent_id'];
  return {
    id: field(row, 'id'),
    number: Number(row['number']),
    name: field(row, 'name'),
    kind: field(row, 'kind'),
    parentId: typeof parent === 'string' ? parent : null,
    isActive: row['is_active'] === true,
    sizeBytes: Number(row['size_bytes']),
    fullSizeBytes: Number(row['full_size_bytes']),
  };
}

export async function versionsOf(api: MesbahApi, project: string): Promise<readonly VersionRow[]> {
  return rows(await api.get(`/api/versions/?project=${project}&page_size=200`)).map(toVersion);
}

export function numbered(versions: readonly VersionRow[], number: number): VersionRow {
  const found = versions.find((version) => version.number === number);
  if (!found) {
    throw new Error(`the project has no v${number}`);
  }
  return found;
}

export function versionTitle(version: VersionRow, locale: UiLocale): string {
  const seeded = version.number === ROOT_NUMBER && version.name === SEEDED_ROOT_NAME;
  return `v${version.number} · ${seeded ? text('core', locale, 'version.baseName') : version.name}`;
}

export async function slugOf(api: MesbahApi, project: string): Promise<string> {
  return field(await api.get(`/api/projects/${project}/`), 'slug');
}

export async function repoOf(api: MesbahApi, model: string): Promise<string> {
  return field(await api.get(`/api/models/${model}/`), 'repo_id');
}
