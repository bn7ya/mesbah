import { randomUUID } from 'node:crypto';

import { request, type APIRequestContext, type APIResponse } from '@playwright/test';

import type { Answer, Operation } from './access.types';
import { isJson } from './api';
import type { Json, Method } from './api.types';
import { stateFile } from './world';
import type { Role } from './world.types';

const WRITES: readonly Method[] = ['POST', 'PUT', 'PATCH', 'DELETE'];
const PATH_PARAMETER = /\{(\w+)\}/g;
const ABSENT_MEMBER = '999999999';

// Given the role's storage state: a context made inside a test otherwise starts from the
// project's, which is the owner's.
export class SavedSession {
  private constructor(private readonly context: APIRequestContext) {}

  static async open(baseUrl: string, role: Role): Promise<SavedSession> {
    const context = await request.newContext({
      baseURL: baseUrl,
      storageState: stateFile(role),
      extraHTTPHeaders: { Referer: `${baseUrl}/` },
    });
    return new SavedSession(context);
  }

  async send(method: Method, path: string, body: Json = {}, multipart = false): Promise<APIResponse> {
    if (method === 'GET') {
      return this.context.fetch(path, { method });
    }
    const headers = { 'X-CSRFToken': await this.token() };
    if (multipart) {
      return this.context.fetch(path, { method, multipart: formOf(body), headers });
    }
    return this.context.fetch(path, { method, data: body, headers });
  }

  async dispose(): Promise<void> {
    await this.context.dispose();
  }

  private async token(): Promise<string> {
    const state = await this.context.storageState();
    return state.cookies.find((cookie) => cookie.name === 'csrftoken')?.value ?? '';
  }
}

export async function withKey(baseUrl: string, key: string): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: baseUrl,
    storageState: { cookies: [], origins: [] },
    extraHTTPHeaders: { Authorization: `Bearer ${key}` },
  });
}

export async function readJson(response: APIResponse): Promise<Json> {
  const body: unknown = await response.json();
  if (!isJson(body)) {
    throw new Error(`expected a JSON object, got ${JSON.stringify(body)}`);
  }
  return body;
}

function formOf(body: Json): Record<string, string> {
  const form: Record<string, string> = { name: 'refused' };
  for (const [key, value] of Object.entries(body)) {
    form[key] = String(value);
  }
  return form;
}

function parse(body: string): unknown {
  try {
    return JSON.parse(body);
  } catch {
    return null;
  }
}

export async function answer(response: APIResponse): Promise<Answer> {
  const body = await response.text();
  const parsed = parse(body);
  const error = isJson(parsed) ? parsed['error'] : null;
  if (!isJson(error)) {
    return { status: response.status(), code: null, message: body.slice(0, 200) };
  }
  return {
    status: response.status(),
    code: typeof error['code'] === 'string' ? error['code'] : null,
    message: typeof error['message'] === 'string' ? error['message'] : '',
  };
}

function isMethod(value: string): value is Method {
  return (WRITES as readonly string[]).includes(value);
}

function parameterTypes(operation: Json): ReadonlyMap<string, string> {
  const found = new Map<string, string>();
  const listed = operation['parameters'];
  for (const parameter of Array.isArray(listed) ? listed.filter(isJson) : []) {
    const schema = parameter['schema'];
    if (parameter['in'] === 'path' && typeof parameter['name'] === 'string') {
      found.set(parameter['name'], isJson(schema) && typeof schema['type'] === 'string' ? schema['type'] : 'string');
    }
  }
  return found;
}

// SessionAuthentication's CSRF check reads request.POST, so a body the view cannot parse is
// refused with 415 before the permission check runs; such an operation is sent as a form.
function onlyMultipart(operation: Json): boolean {
  const body = operation['requestBody'];
  const content = isJson(body) ? body['content'] : null;
  return isJson(content) && Object.keys(content).length > 0 && !('application/json' in content);
}

// A random id: a missing permission check then answers 404 and touches nothing the world owns.
function filled(path: string, types: ReadonlyMap<string, string>): string {
  return path.replace(PATH_PARAMETER, (_match, name: string) =>
    types.get(name) === 'integer' ? ABSENT_MEMBER : randomUUID(),
  );
}

export function writeOperations(schema: Json): Operation[] {
  const paths = schema['paths'];
  if (!isJson(paths)) {
    throw new Error('the schema lists no paths');
  }
  const found: Operation[] = [];
  for (const [path, item] of Object.entries(paths)) {
    if (!path.startsWith('/api/') || !isJson(item)) {
      continue;
    }
    for (const [verb, operation] of Object.entries(item)) {
      const method = verb.toUpperCase();
      if (!isMethod(method) || !isJson(operation) || typeof operation['operationId'] !== 'string') {
        continue;
      }
      found.push({
        id: operation['operationId'],
        method,
        path,
        url: filled(path, parameterTypes(operation)),
        multipart: onlyMultipart(operation),
      });
    }
  }
  return found;
}
