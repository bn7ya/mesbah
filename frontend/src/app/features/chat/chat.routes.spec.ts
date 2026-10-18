import { UrlSegment } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { conversationMatcher, routes } from './chat.routes';
import { chatGuard } from './guards/chat.guard';

describe('chat routes', () => {
  it('matches the bare chat path, with no conversation open', () => {
    expect(conversationMatcher([])).toEqual({ consumed: [] });
  });

  it('matches one more segment as the conversation', () => {
    const segment = new UrlSegment('0f47bfe3-140b-4983-a77e-fd37445d49d0', {});

    const result = conversationMatcher([segment]);

    expect(result?.consumed).toEqual([segment]);
    expect(result?.posParams?.['conversationId']).toBe(segment);
  });

  it('matches nothing deeper', () => {
    expect(conversationMatcher([new UrlSegment('a', {}), new UrlSegment('b', {})])).toBeNull();
  });

  it('serves both urls from one route, behind the guard', () => {
    expect(routes).toHaveLength(1);
    expect(routes[0].matcher).toBe(conversationMatcher);
    expect(routes[0].canActivate).toEqual([chatGuard]);
  });
});
