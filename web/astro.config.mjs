// @ts-check
import { defineConfig } from 'astro/config';

// GitHub Pages serves the project at https://simonvanherweghe.github.io/cogncur/
export default defineConfig({
  site: 'https://simonvanherweghe.github.io',
  base: '/cogncur',
  trailingSlash: 'ignore',
  vite: {
    // harfbuzzjs uses top-level await and finds its .wasm via new URL(…, import.meta.url):
    // build for es2022 and don't pre-bundle it in dev (pre-bundling breaks that URL).
    build: { target: 'es2022' },
    optimizeDeps: { exclude: ['harfbuzzjs'] },
  },
});
