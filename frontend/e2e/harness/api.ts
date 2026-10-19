import { expect, request, type APIRequestContext, type APIResponse } from '@playwright/test';

import type { Json, Method, Upload } from './api.types';

export function isJson(value: unknown): value is Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function field(value: Json, key: string): string {
  const found = value[key];
  if (typeof found !== 'string') {
    throw new Error(`expected a string at ${key} in ${JSON.stringify(value)}`);
  }
  return found;
}

export function rows(value: Json, key = 'results'): Json[] {
  const found = value[key];
  return Array.isArray(found) ? found.filter(isJson) : [];
}

export class MesbahApi {
  private constructor(
    readonly context: APIRequestContext,
    private readonly baseUrl: string,
  ) {}

  static async open(baseUrl: string): Promise<MesbahApi> {
    // Inside a test the request context takes the project's saved session unless told not
    // to, and signing in as someone else would then end that session for every later test.
    const context = await request.newContext({
      baseURL: baseUrl,
      extraHTTPHeaders: { Referer: `${baseUrl}/` },
      storageState: { cookies: [], origins: [] },
    });
    const api = new MesbahApi(context, baseUrl);
    await api.get('/api/auth/csrf/');
    return api;
  }

  static async signIn(baseUrl: string, username: string, password: string): Promise<MesbahApi> {
    const api = await MesbahApi.open(baseUrl);
    await api.post('/api/auth/login/', { username, password });
    return api;
  }

  async get(path: string): Promise<Json> {
    return this.call('GET', path);
  }

  async post(path: string, body: unknown = {}): Promise<Json> {
    return this.call('POST', path, body);
  }

  async patch(path: string, body: unknown): Promise<Json> {
    return this.call('PATCH', path, body);
  }

  async delete(path: string): Promise<Json> {
    return this.call('DELETE', path);
  }

  async call(method: Method, path: string, body?: unknown): Promise<Json> {
    return this.read(await this.send(method, path, body), method, path);
  }

  async send(method: Method, path: string, body?: unknown): Promise<APIResponse> {
    const headers: Record<string, string> =
      method === 'GET' ? {} : { 'X-CSRFToken': await this.csrfToken() };
    return this.context.fetch(path, { method, data: body, headers });
  }

  async upload(path: string, file: Upload, fields: Readonly<Record<string, string>> = {}): Promise<Json> {
    const response = await this.context.post(path, {
      multipart: { ...fields, file },
      headers: { 'X-CSRFToken': await this.csrfToken() },
    });
    return this.read(response, 'POST', path);
  }

  async until(path: string, done: (body: Json) => boolean, timeout = 90_000): Promise<Json> {
    let last: Json = {};
    await expect
      .poll(
        async () => {
          last = await this.get(path);
          return done(last);
        },
        { timeout, intervals: [250, 500, 1000] },
      )
      .toBe(true);
    return last;
  }

  async saveState(path: string): Promise<void> {
    await this.context.storageState({ path });
  }

  async dispose(): Promise<void> {
    await this.context.dispose();
  }

  private async csrfToken(): Promise<string> {
    const state = await this.context.storageState();
    return state.cookies.find((cookie) => cookie.name === 'csrftoken')?.value ?? '';
  }

  private async read(response: APIResponse, method: Method, path: string): Promise<Json> {
    const body = await response.text();
    if (!response.ok()) {
      throw new Error(`${method} ${path} answered ${response.status()}: ${body.slice(0, 500)}`);
    }
    if (!body) {
      return {};
    }
    const parsed: unknown = JSON.parse(body);
    return isJson(parsed) ? parsed : { results: parsed };
  }

  get base(): string {
    return this.baseUrl;
  }
}
