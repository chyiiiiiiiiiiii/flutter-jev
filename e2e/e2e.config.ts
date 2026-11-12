import type { E2EConfig } from 'e2e';
import { mobile } from '@e2e-dev/mobile';
import { decisionExecutor } from '@e2e-dev/decision';
import { typeSafeAi } from '@ai-sdk/typesafe-ai';
import { google } from '@ai-sdk/google';

// The same small model the runner uses: it drives on its own in the `lite`
// arm and only writes field values in the `jev` arm.
const lite = google('gemini-3.1-flash-lite');

export default {
  targets: [
    {
      name: 'iphone',
      engine: mobile({ platform: 'ios', device: process.env.E2E_DEVICE ?? 'iPhone 17e' }),
      // The chaos build is the next version of the same app, not another app,
      // so it keeps the identity and meets the recordings made before it.
      app: { bundleId: 'dev.yii.boxtide', identity: 'boxtide' },
    },
  ],
  workers: 1,
  agents: {
    lite: { model: lite },
    jev: {
      executor: decisionExecutor({
        model: typeSafeAi.decisionModel('jev-latest'),
        textModel: lite,
      }),
    },
    // Same pair with screenshots: can tap and type on controls the tree
    // does not list, which is what Flutter's fields look like on iOS.
    jevv: {
      executor: decisionExecutor({
        model: typeSafeAi.decisionModel('jev-latest'),
        textModel: lite,
        vision: true,
      }),
    },
  },
} satisfies E2EConfig;
