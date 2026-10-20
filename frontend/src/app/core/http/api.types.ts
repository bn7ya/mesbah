export interface Page<T> {
  readonly count: number;
  readonly next: string | null;
  readonly previous: string | null;
  readonly results: readonly T[];
}

export interface PageQuery {
  readonly page?: number;
  readonly page_size?: number;
  readonly ordering?: string;
  readonly search?: string;
}

export interface ApiError {
  readonly code: string;
  readonly message: string;
  readonly fields?: Readonly<Record<string, readonly string[]>>;
}

export interface ApiErrorResponse {
  readonly error: ApiError;
}

export const EMPTY_PAGE: Page<never> = {
  count: 0,
  next: null,
  previous: null,
  results: [],
};
