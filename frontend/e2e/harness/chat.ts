import { field, type MesbahApi } from './api';

export async function startConversation(api: MesbahApi, project: string, title?: string): Promise<string> {
  return field(await api.post('/api/chat/', title === undefined ? { project } : { project, title }), 'id');
}

export async function ask(api: MesbahApi, conversation: string, content: string): Promise<void> {
  const response = await api.send('POST', `/api/chat/${conversation}/reply/`, { content });
  const body = await response.text();
  if (!response.ok() || !body.includes('event: done')) {
    throw new Error(`the reply to "${content}" did not finish: ${response.status()} ${body.slice(-500)}`);
  }
}
