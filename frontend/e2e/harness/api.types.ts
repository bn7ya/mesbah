export interface Json {
  readonly [key: string]: unknown;
}

export type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

export interface Upload {
  readonly name: string;
  readonly mimeType: string;
  readonly buffer: Buffer;
}
