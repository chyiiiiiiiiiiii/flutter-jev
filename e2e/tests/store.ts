import { execFileSync } from 'node:child_process';
import { appendFileSync, mkdirSync } from 'node:fs';

// e2e sees the screen, not the store. Record what the app really holds so a
// green test and a done task can be told apart afterwards.
export function recordStore(flow: string) {
  mkdirSync('../results/e2e', { recursive: true });
  const line = execFileSync('python3.13', ['state_check.py', flow, '--label', process.env.RUN_LABEL ?? ''], {
    encoding: 'utf8',
  });
  appendFileSync(`../results/e2e/store-${process.env.RUN_LABEL ?? 'unlabelled'}.jsonl`, line);
}
