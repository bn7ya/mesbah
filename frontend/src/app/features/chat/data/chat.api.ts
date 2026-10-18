import {
  HttpClient,
  HttpEventType,
  HttpParams,
  type HttpEvent,
} from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { EMPTY, concatMap, defer, from, map, type Observable } from 'rxjs';

import type { Page } from '@core/http/api.types';
import {
  CONVERSATIONS_PAGE_SIZE,
  ENGINES_PAGE_SIZE,
  PAGE_SIZE,
  type Conversation,
  type ConversationChange,
  type EngineOption,
  type Message,
  type MessageEdit,
  type MessagePart,
  type NewConversation,
  type ProjectDefaults,
  type ReplyEvent,
  type VersionOption,
} from './chat.types';
import { parseFrames, toReplyEvent } from './sse';

@Injectable({ providedIn: 'root' })
export class ChatApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/chat';

  conversations(project: string, page: number): Observable<Page<Conversation>> {
    const params = new HttpParams({ fromObject: { project, page, page_size: CONVERSATIONS_PAGE_SIZE } });
    return this.http.get<Page<Conversation>>(`${this.base}/`, { params });
  }

  conversation(id: string): Observable<Conversation> {
    return this.http.get<Conversation>(`${this.base}/${id}/`);
  }

  create(conversation: NewConversation): Observable<Conversation> {
    return this.http.post<Conversation>(`${this.base}/`, conversation);
  }

  change(id: string, change: ConversationChange): Observable<Conversation> {
    return this.http.patch<Conversation>(`${this.base}/${id}/`, change);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/`);
  }

  messages(conversation: string, page: number): Observable<Page<Message>> {
    const params = new HttpParams({ fromObject: { page, page_size: PAGE_SIZE } });
    return this.http.get<Page<Message>>(`${this.base}/${conversation}/messages/`, { params });
  }

  message(id: string): Observable<Message> {
    return this.http.get<Message>(`${this.base}/messages/${id}/`);
  }

  edit(id: string, edit: MessageEdit): Observable<Message> {
    return this.http.patch<Message>(`${this.base}/messages/${id}/`, edit);
  }

  restore(id: string, part: MessagePart, seen: string): Observable<Message> {
    return this.http.post<Message>(`${this.base}/messages/${id}/restore/`, { seen, part });
  }

  approve(id: string, approved: boolean): Observable<Message> {
    return this.http.post<Message>(`${this.base}/messages/${id}/approve/`, { approved });
  }

  reply(conversation: string, content: string): Observable<ReplyEvent> {
    return defer(() => {
      let consumed = 0;
      return this.http
        .post(
          `${this.base}/${conversation}/reply/`,
          { content },
          { observe: 'events', reportProgress: true, responseType: 'text' },
        )
        .pipe(
          concatMap((event: HttpEvent<string>) => {
            const text = textSoFar(event);
            if (text === null) {
              return EMPTY;
            }
            const parsed = parseFrames(text, consumed);
            consumed = parsed.next;
            return from(parsed.frames.map(toReplyEvent).filter((reply) => reply !== null));
          }),
        );
    });
  }

  project(id: string): Observable<ProjectDefaults> {
    return this.http
      .get<ProjectDefaults>(`/api/projects/${id}/`)
      .pipe(map(({ system_prompt, thinking, generation }) => ({ system_prompt, thinking, generation })));
  }

  versions(project: string, page: number): Observable<Page<VersionOption>> {
    const params = new HttpParams({ fromObject: { project, page, page_size: PAGE_SIZE } });
    return this.http.get<Page<VersionOption>>('/api/versions/', { params });
  }

  engines(): Observable<readonly EngineOption[]> {
    const params = new HttpParams({ fromObject: { page_size: ENGINES_PAGE_SIZE } });
    return this.http.get<Page<EngineOption>>('/api/serving/engines/', { params }).pipe(
      map((page) =>
        page.results
          .filter((engine) => engine.enabled)
          .map(({ id, name, enabled, is_default }) => ({ id, name, enabled, is_default })),
      ),
    );
  }
}

function textSoFar(event: HttpEvent<string>): string | null {
  if (event.type === HttpEventType.DownloadProgress) {
    return event.partialText ?? null;
  }
  if (event.type === HttpEventType.Response) {
    return event.body;
  }
  return null;
}
