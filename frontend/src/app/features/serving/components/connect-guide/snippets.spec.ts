import { describe, expect, it } from 'vitest';

import { guideFor } from './snippets';

describe('guideFor', () => {
  const [openai, ollama] = guideFor('https://mesbah.example', 'support-assistant');

  it('gives each API its base address under the origin', () => {
    expect(openai.address).toBe('https://mesbah.example/v1');
    expect(ollama.address).toBe('https://mesbah.example/ollama');
  });

  it('has a Python and a curl snippet for each, naming the project and the placeholder key', () => {
    for (const api of [openai, ollama]) {
      expect(api.snippets.map((snippet) => snippet.id)).toEqual(['python', 'curl']);
      for (const snippet of api.snippets) {
        expect(snippet.code).toContain('support-assistant');
        expect(snippet.code).toContain('msb_…');
        expect(snippet.code).toContain(api.address);
      }
    }
  });

  it('asks Ollama for one whole answer', () => {
    expect(ollama.snippets[1].code).toContain('"stream": false');
  });
});
