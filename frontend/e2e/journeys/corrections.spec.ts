import type { Locator } from '@playwright/test';

import { ask, startConversation } from '../harness/chat';
import { stamp } from '../harness/copy';
import { expect, test } from '../harness/fixtures';
import { choose } from '../harness/pages';
import { createProject } from '../harness/seed';

const WORDS = {
  en: {
    project: 'Corrections journey',
    first: 'Which lamp gives the most light',
    second: 'Is olive oil a good fuel',
    corrected: 'The brass lamp with the widest wick.',
    thinking: 'A wider wick draws up more oil at once.',
  },
  ar: {
    project: 'رحلة التصحيح',
    first: 'أي مصباح يعطي أكثر ضوء',
    second: 'هل زيت الزيتون وقود جيد',
    corrected: 'المصباح النحاسي ذو الفتيل الأعرض.',
    thinking: 'الفتيل الأعرض يسحب زيتا أكثر في وقت واحد.',
  },
} as const;

test('replies are corrected in place, become training examples, and a viewer only reads them', async ({
  page,
  t,
  locale,
  world,
  owner,
  as,
  shot,
}) => {
  test.slow();
  const words = WORDS[locale];
  const mark = stamp();
  const first = `${words.first} ${mark}`;
  const second = `${words.second} ${mark}`;
  const project = await createProject(owner, `${words.project} ${mark}`, world.baseModel);
  const conversation = await startConversation(owner, project);
  await ask(owner, conversation, first);
  await ask(owner, conversation, second);
  await page.goto(`/projects/${project}/chat/${conversation}`);

  const replies = page
    .getByRole('region', { name: t('chat', 'chat.messages.label') })
    .getByRole('article', { name: t('chat', 'chat.sender.model') });
  const firstReply = replies.nth(0);
  const secondReply = replies.nth(1);
  const actions = (reply: Locator): Locator => reply.getByRole('button', { name: t('chat', 'chat.menu.label') });
  await expect(firstReply.getByText(`Reply from base: ${first}`, { exact: true })).toBeVisible();

  await test.step('the reply is edited where it stands', async () => {
    await choose(actions(firstReply), page.getByRole('menuitem', { name: t('chat', 'chat.menu.editReply') }));
    const editor = firstReply.getByRole('textbox', { name: t('chat', 'chat.edit.replyLabel') });
    await expect(editor).toBeFocused();
    await editor.fill(words.corrected);
    await firstReply.getByRole('button', { name: t('core', 'actions.save') }).click();

    await expect(firstReply.getByText(words.corrected, { exact: true })).toBeVisible();
    await expect(firstReply.getByText(t('chat', 'chat.marks.edited'))).toBeVisible();
    await expect(firstReply.getByText(t('chat', 'chat.marks.approved'))).toBeVisible();
  });

  await test.step('its thinking is added on its own', async () => {
    await choose(actions(firstReply), page.getByRole('menuitem', { name: t('chat', 'chat.menu.addThinking') }));
    await firstReply.getByRole('textbox', { name: t('chat', 'chat.edit.thinkingLabel') }).fill(words.thinking);
    await firstReply.getByRole('button', { name: t('core', 'actions.save') }).click();

    await expect(firstReply.getByText(t('chat', 'chat.marks.thinkingEdited'))).toBeVisible();
    await expect(firstReply.getByText(words.thinking, { exact: true })).toBeVisible();
    await expect(firstReply.getByText(words.corrected, { exact: true })).toBeVisible();
  });

  await test.step('the other reply is approved as it is', async () => {
    await choose(actions(secondReply), page.getByRole('menuitem', { name: t('chat', 'chat.menu.approve') }));

    await expect(page.getByText(t('chat', 'chat.approval.given'))).toBeVisible();
    await expect(secondReply.getByText(t('chat', 'chat.marks.approved'))).toBeVisible();
    await expect(secondReply.getByText(t('chat', 'chat.marks.edited'))).toHaveCount(0);
    await shot('a corrected reply and an approved one');
  });

  await test.step('both are examples on the Training tab', async () => {
    await page
      .getByRole('tablist', { name: t('projects', 'projects.tabs.label') })
      .getByRole('tab', { name: t('projects', 'projects.tabs.training') })
      .click();
    await expect(page).toHaveURL(/\/training$/);
    await page.getByRole('radio', { name: t('training', 'training.views.examples') }).click();

    const examples = page.getByRole('list', { name: t('training', 'training.examples.list') }).locator(':scope > li');
    await expect(examples).toHaveCount(2);
    const corrected = examples.filter({ hasText: words.corrected }).filter({ hasNotText: second });
    await expect(corrected).toHaveCount(1);
    await expect(corrected.getByText(t('training', 'training.examples.corrected'))).toBeVisible();
    await expect(corrected.getByText(t('training', 'training.examples.thinkingCorrected'))).toBeVisible();
    await expect(corrected.getByText(words.thinking, { exact: true })).toBeVisible();
    const asIs = examples.filter({ hasText: `Reply from base: ${second}` });
    await expect(asIs.getByText(t('training', 'training.examples.asIs'))).toBeVisible();
    await shot('the examples a run learns from');
  });

  await test.step("the model's reply is restored after asking", async () => {
    await page
      .getByRole('tablist', { name: t('projects', 'projects.tabs.label') })
      .getByRole('tab', { name: t('projects', 'projects.tabs.chat') })
      .click();
    await page
      .getByRole('navigation', { name: t('chat', 'chat.list.title') })
      .getByRole('link')
      .filter({ hasText: first })
      .click();
    const asking = page.getByRole('dialog', { name: t('chat', 'chat.restore.replyTitle') });

    await choose(actions(firstReply), page.getByRole('menuitem', { name: t('chat', 'chat.menu.restoreReply') }));
    await asking.getByRole('button', { name: t('core', 'actions.cancel') }).click();
    await expect(asking).toHaveCount(0);
    await expect(firstReply.getByText(words.corrected, { exact: true })).toBeVisible();

    await choose(actions(firstReply), page.getByRole('menuitem', { name: t('chat', 'chat.menu.restoreReply') }));
    await expect(asking).toBeVisible();
    await shot('asked before restoring');
    await asking.getByRole('button', { name: t('chat', 'chat.restore.confirm') }).click();

    await expect(firstReply.getByText(`Reply from base: ${first}`, { exact: true })).toBeVisible();
    await expect(firstReply.getByText(t('chat', 'chat.marks.edited'))).toHaveCount(0);
    await expect(firstReply.getByText(t('chat', 'chat.marks.thinkingEdited'))).toBeVisible();
  });

  await test.step('a viewer reads the conversation and cannot correct it', async () => {
    const viewer = await as('viewer');
    await viewer.goto(`/projects/${project}/chat/${conversation}`);
    const seen = viewer
      .getByRole('region', { name: t('chat', 'chat.messages.label') })
      .getByRole('article', { name: t('chat', 'chat.sender.model') });

    await expect(seen.nth(0).getByText(`Reply from base: ${first}`, { exact: true })).toBeVisible();
    await expect(seen.nth(1).getByText(t('chat', 'chat.marks.approved'))).toBeVisible();
    await expect(seen.nth(0).getByRole('button', { name: t('chat', 'chat.menu.copy') })).toBeVisible();
    await expect(viewer.getByRole('button', { name: t('chat', 'chat.menu.label') })).toHaveCount(0);
    await expect(viewer.getByText(t('chat', 'chat.composer.readOnly'))).toBeVisible();
    await expect(viewer.getByRole('textbox', { name: t('chat', 'chat.composer.label') })).toHaveCount(0);
    await expect(viewer.getByRole('button', { name: t('chat', 'chat.list.new') })).toHaveCount(0);
  });
});
