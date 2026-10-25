import { test } from '@e2e-dev/mobile';
import { expect } from 'e2e';
import { recordStore } from './store';

// The decision executor only offers `type` on text boxes, and on iOS every
// Flutter text field reports as "Other" (REPORT.md project H; probe in notes/semprobe_main.dart),
// so Jev cannot sign in. Here sign-in is plain locators and the agent gets the
// two flows that need only taps, the same goal for either agent.

async function signIn(screen: Parameters<Parameters<typeof test>[1]>[0]['screen']) {
  await screen.getByTestId('email_field').fill('demo@example.com');
  // The first fill on Flutter's obscured field kills the XCTest runner session;
  // the field is focused by then, so a second fill lands. The LLM agent does
  // the same thing on its own: type, see the screen change, type again.
  const password = screen.getByTestId('password_field');
  try {
    await password.fill('hunter2');
  } catch {
    await password.fill('hunter2');
  }
  await screen.getByTestId('signin_button').tap();
  await expect(screen.getByRole('button', /^Orders/)).toBeVisible();
}

test('taps return-flow', async ({ app, agent, screen }) => {
  await app.open();
  await signIn(screen);
  await agent.act('Open order {order} and submit a return request for it, finishing every step of the return form', {
    params: { order: '5207' },
  });
  await expect(screen.getByText('Return started').first()).toBeVisible();
  recordStore('return-flow');
});

test('taps cart-flow', async ({ app, agent, screen }) => {
  await app.open();
  await signIn(screen);
  await agent.act('Add the pocket speaker to the cart, then open the cart');
  await expect(screen.getByTestId('cart_remove_p-speaker')).toBeVisible();
  recordStore('cart-flow');
});
