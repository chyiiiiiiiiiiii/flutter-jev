import { test } from '@e2e-dev/mobile';
import { expect } from 'e2e';
import { recordStore } from './store';

// On e2e 0.23 and iOS 27.2 an agent's `type` into Flutter's obscured password
// field fails every time, whichever model picks it. Sign-in is plain locators
// here, so the agent is judged on the four flows themselves.

async function signIn(screen: Parameters<Parameters<typeof test>[1]>[0]['screen']) {
  await screen.getByTestId('email_field').fill('demo@example.com');
  const password = screen.getByTestId('password_field');
  try {
    await password.fill('hunter2');
  } catch {
    await password.fill('hunter2');
  }
  await screen.getByTestId('signin_button').tap();
  await expect(screen.getByRole('button', /^Orders/)).toBeVisible();
}

test('login return-flow', async ({ app, agent, screen }) => {
  await app.open();
  await signIn(screen);
  await agent.act('Open order {order} and submit a return request for it, finishing every step of the return form', {
    params: { order: '5207' },
  });
  await expect(screen.getByText('Return started').first()).toBeVisible();
  recordStore('return-flow');
});

test('login cart-flow', async ({ app, agent, screen }) => {
  await app.open();
  await signIn(screen);
  await agent.act('Add the pocket speaker to the cart, then open the cart');
  await expect(screen.getByTestId('cart_remove_p-speaker')).toBeVisible();
  recordStore('cart-flow');
});

test('login support-flow', async ({ app, agent, screen }) => {
  await app.open();
  await signIn(screen);
  await agent.act('Contact support about order {order} with the message {message}', {
    params: { order: '5213', message: 'My parcel has not moved in four days.' },
  });
  await expect(screen.getByText('Message sent').first()).toBeVisible();
  recordStore('support-flow');
});

test('login address-flow', async ({ app, agent, screen }) => {
  await app.open();
  await signIn(screen);
  await agent.act('Add a new saved delivery address labelled {label} at {lines}', {
    params: { label: 'Office', lines: '9F, 100 Taiyuan Rd' },
  });
  await expect(screen.getByText(/^Office/).first()).toBeVisible();
  recordStore('address-flow');
});
