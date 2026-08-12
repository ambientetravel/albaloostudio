import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * `npm run share` sets VITE_TEST_BUILD=1, which swaps in the real feedback
 * widget. Every other build gets a stub, so the widget is absent from the
 * bundle rather than merely unrendered.
 */
const TEST_BUILD = process.env.VITE_TEST_BUILD === '1';
const feedback = fileURLToPath(
  new URL(TEST_BUILD ? './src/dev/Feedback.tsx' : './src/dev/FeedbackOff.tsx', import.meta.url),
);

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@feedback': feedback } },
  define: { __TEST_BUILD__: JSON.stringify(TEST_BUILD) },
  base: './',
  server: { port: 5183, strictPort: false },
  build: { target: 'es2022', sourcemap: true },
});
