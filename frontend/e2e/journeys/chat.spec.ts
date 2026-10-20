import { rows } from '../harness/api';
import { stamp, text } from '../harness/copy';
import { expect, test } from '../harness/fixtures';

const QUESTIONS = {
  en: { short: 'What does a lamp do', long: 'Tell me a long story' },
  ar: { short: 'ما عمل المصباح', long: 'احك لي قصة طويلة' },
} as const;
const CONVERSATION = /\/chat\/([0-9a-f-]{36})$/;

test('a new conversation streams the reply to a question', async ({ page, t, locale, world, shot }) => {
  const question = `${QUESTIONS[locale].short} ${stamp()}`;
  await page.goto(`/projects/${world.projects[locale].chat}/chat`);

  await page.getByRole('button', { name: t('chat', 'chat.list.new') }).click();
  await expect(page).toHaveURL(CONVERSATION);
  await page.getByRole('textbox', { name: t('chat', 'chat.composer.label') }).fill(question);
  await page.getByRole('button', { name: t('chat', 'chat.composer.send') }).click();

  const messages = page.getByRole('region', { name: t('chat', 'chat.messages.label') });
  await expect(messages.getByRole('article', { name: t('chat', 'chat.sender.you') })).toHaveText(new RegExp(question));
  const reply = messages.getByRole('article', { name: t('chat', 'chat.sender.model') });
  await expect(reply.getByText(`Reply from base: ${question}`, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: t('chat', 'chat.composer.send') })).toBeVisible();
  await expect(reply.getByText(t('chat', 'chat.stream.writing'))).toHaveCount(0);
  const listed = page
    .getByRole('navigation', { name: t('chat', 'chat.list.title') })
    .getByRole('link')
    .filter({ hasText: question });
  await expect(listed).toContainText(text('chat', locale, 'chat.list.messages', { count: 2 }));
  await shot('a reply');
});

test('a long reply stopped while it streams keeps what it wrote', async ({ page, t, locale, world, owner, shot }) => {
  test.slow();
  const question = `${QUESTIONS[locale].long} [long] ${stamp()}`;
  await page.goto(`/projects/${world.projects[locale].chat}/chat`);
  await page.getByRole('button', { name: t('chat', 'chat.list.new') }).click();
  await expect(page).toHaveURL(CONVERSATION);
  const conversation = CONVERSATION.exec(page.url())?.[1] ?? '';

  const field = page.getByRole('textbox', { name: t('chat', 'chat.composer.label') });
  await field.fill(question);
  await field.press('Enter');
  const messages = page.getByRole('region', { name: t('chat', 'chat.messages.label') });
  const reply = messages.getByRole('article', { name: t('chat', 'chat.sender.model') });
  await expect(reply).toContainText('word5');
  await shot('a long reply streaming');
  await page.getByRole('button', { name: t('chat', 'chat.composer.stop') }).click();

  await expect(page.getByRole('button', { name: t('chat', 'chat.composer.send') })).toBeVisible();
  await expect(reply.getByText(t('chat', 'chat.marks.stopped'))).toBeVisible();
  const saved = await owner.until(`/api/chat/${conversation}/messages/`, (body) => rows(body).at(-1)?.['status'] === 'stopped');
  const kept = String(rows(saved).at(-1)?.['content']);
  expect(kept.startsWith(`Reply from base: ${question} word1`)).toBe(true);
  expect(kept).not.toContain('word600');
  const written = reply.getByText(/^Reply from base: /);
  await expect(written).toHaveText(kept);
  await shot('a stopped reply');

  await page.reload();
  await expect(written).toHaveText(kept);
  await expect(reply.getByText(t('chat', 'chat.marks.stopped'))).toBeVisible();
  await expect(page.getByRole('button', { name: t('chat', 'chat.composer.send') })).toBeVisible();
});
