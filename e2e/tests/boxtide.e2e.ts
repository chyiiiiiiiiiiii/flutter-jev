import { execFileSync } from 'node:child_process';
import { appendFileSync, mkdirSync } from 'node:fs';
import { test } from '@e2e-dev/mobile';
import { expect } from 'e2e';

// The four flows `runner/arms.py` judges, written the way e2e wants them:
// a goal for the agent, then a check the agent cannot talk its way past.
// Checks read titles and fixed test ids, which the chaos build leaves alone;
// it renames keys, swaps button labels, reorders the order list and may add a
// step. Flutter names a tab "Orders\nTab 2 of 5", hence the patterns.

const signIn = { email: 'demo@example.com', password: 'hunter2' };

// e2e sees the screen, not the store. Record what the app really holds so a
// green test and a done task can be told apart afterwards.
function recordStore(flow: string) {
  mkdirSync('../results/e2e', { recursive: true });
  const line = execFileSync('python3.13', ['state_check.py', flow, '--label', process.env.RUN_LABEL ?? ''], {
    encoding: 'utf8',
  });
  appendFileSync(`../results/e2e/store-${process.env.RUN_LABEL ?? 'unlabelled'}.jsonl`, line);
}

test('return-flow', async ({ app, agent, screen }) => {
  await app.open();
  await agent.act('Sign in with email {email} and password {password}', { params: signIn });
  await expect(screen.getByRole('button', /^Orders/)).toBeVisible();
  await agent.act('Open order {order} and submit a return request for it, finishing every step of the return form', {
    params: { order: '5207' },
  });
  await expect(screen.getByText('Return started').first()).toBeVisible();
  recordStore('return-flow');
});

test('cart-flow', async ({ app, agent, screen }) => {
  await app.open();
  await agent.act('Sign in with email {email} and password {password}', { params: signIn });
  await expect(screen.getByRole('button', /^Orders/)).toBeVisible();
  await agent.act('Add the pocket speaker to the cart, then open the cart');
  await expect(screen.getByTestId('cart_remove_p-speaker')).toBeVisible();
  recordStore('cart-flow');
});

test('support-flow', async ({ app, agent, screen }) => {
  await app.open();
  await agent.act('Sign in with email {email} and password {password}', { params: signIn });
  await expect(screen.getByRole('button', /^Orders/)).toBeVisible();
  await agent.act('Contact support about order {order} with the message {message}', {
    params: { order: '5213', message: 'My parcel has not moved in four days.' },
  });
  await expect(screen.getByText('Message sent').first()).toBeVisible();
  recordStore('support-flow');
});

test('address-flow', async ({ app, agent, screen }) => {
  await app.open();
  await agent.act('Sign in with email {email} and password {password}', { params: signIn });
  await expect(screen.getByRole('button', /^Orders/)).toBeVisible();
  await agent.act('Add a new saved delivery address labelled {label} at {lines}', {
    params: { label: 'Office', lines: '9F, 100 Taiyuan Rd' },
  });
  await expect(screen.getByText(/^Office/).first()).toBeVisible();
  recordStore('address-flow');
});
