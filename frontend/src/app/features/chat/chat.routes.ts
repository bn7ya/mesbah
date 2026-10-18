import type { Routes, UrlMatchResult, UrlSegment } from '@angular/router';

import { provideTranslations } from '@core/i18n/provide-translations';
import { chatGuard } from './guards/chat.guard';
import ar from './i18n/ar.json';
import en from './i18n/en.json';
import { ConversationStore } from './state/conversation.store';
import { ConversationsStore } from './state/conversations.store';

export function conversationMatcher(segments: UrlSegment[]): UrlMatchResult | null {
  if (segments.length === 0) {
    return { consumed: [] };
  }
  if (segments.length === 1) {
    return { consumed: segments, posParams: { conversationId: segments[0] } };
  }
  return null;
}

export const routes: Routes = [
  {
    matcher: conversationMatcher,
    canActivate: [chatGuard],
    providers: [ConversationsStore, ConversationStore, provideTranslations(en, ar)],
    loadComponent: () => import('./pages/chat/chat').then((m) => m.ChatPage),
  },
];
