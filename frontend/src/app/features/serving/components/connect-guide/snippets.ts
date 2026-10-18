import { KEY_PLACEHOLDER, type GuideApi } from '../../data/serving.types';

const PROMPT = 'Hello';

export function guideFor(origin: string, slug: string): readonly GuideApi[] {
  const openai = `${origin}/v1`;
  const ollama = `${origin}/ollama`;
  return [
    {
      id: 'openai',
      address: openai,
      snippets: [
        {
          id: 'python',
          labelKey: 'serving.guide.python',
          code: [
            'from openai import OpenAI',
            '',
            `client = OpenAI(base_url="${openai}", api_key="${KEY_PLACEHOLDER}")`,
            'reply = client.chat.completions.create(',
            `    model="${slug}",`,
            `    messages=[{"role": "user", "content": "${PROMPT}"}],`,
            ')',
            'print(reply.choices[0].message.content)',
          ].join('\n'),
        },
        {
          id: 'curl',
          labelKey: 'serving.guide.curl',
          code: [
            `curl ${openai}/chat/completions \\`,
            `  -H "Authorization: Bearer ${KEY_PLACEHOLDER}" \\`,
            '  -H "Content-Type: application/json" \\',
            `  -d '{"model": "${slug}", "messages": [{"role": "user", "content": "${PROMPT}"}]}'`,
          ].join('\n'),
        },
      ],
    },
    {
      id: 'ollama',
      address: ollama,
      snippets: [
        {
          id: 'python',
          labelKey: 'serving.guide.python',
          code: [
            'from ollama import Client',
            '',
            `client = Client(host="${ollama}", headers={"Authorization": "Bearer ${KEY_PLACEHOLDER}"})`,
            'reply = client.chat(',
            `    model="${slug}",`,
            `    messages=[{"role": "user", "content": "${PROMPT}"}],`,
            ')',
            'print(reply.message.content)',
          ].join('\n'),
        },
        {
          id: 'curl',
          labelKey: 'serving.guide.curl',
          code: [
            `curl ${ollama}/api/chat \\`,
            `  -H "Authorization: Bearer ${KEY_PLACEHOLDER}" \\`,
            `  -d '{"model": "${slug}", "messages": [{"role": "user", "content": "${PROMPT}"}], "stream": false}'`,
          ].join('\n'),
        },
      ],
    },
  ];
}
