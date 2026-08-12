/**
 * Runs the Vite dev server and the matchmaking server together, so `npm run dev`
 * gives a fully playable game including online mode. Killing either one takes
 * the other down, which avoids a stale server lingering between sessions.
 */
import { spawn } from 'node:child_process';

const procs = [
  { name: 'server', cmd: 'node', args: ['server/index.ts'] },
  { name: 'vite', cmd: 'npx', args: ['vite', ...process.argv.slice(2)] },
];

const children = procs.map(({ name, cmd, args }) => {
  const child = spawn(cmd, args, { stdio: 'inherit', env: { ...process.env, FORCE_COLOR: '1' } });
  child.on('exit', (code) => {
    console.log(`[dev] ${name} exited (${code})`);
    shutdown();
  });
  return child;
});

let closing = false;
function shutdown() {
  if (closing) return;
  closing = true;
  for (const c of children) {
    if (c.exitCode === null) c.kill('SIGTERM');
  }
  setTimeout(() => process.exit(0), 200);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
