import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { readFileSync } from 'node:fs';

const favicon = readFileSync(new URL('./public/favicon.svg', import.meta.url), 'utf8');
const fontNotices = JSON.stringify({
  'DM Sans': readFileSync(new URL('./node_modules/@fontsource/dm-sans/LICENSE', import.meta.url), 'utf8'),
  Manrope: readFileSync(new URL('./node_modules/@fontsource/manrope/LICENSE', import.meta.url), 'utf8'),
}).replaceAll('<', '\\u003c');

// This is an evidence viewer, not a substitute for the Python analysis engine.
// Every asset and the actual generated demo result are bundled into one HTML file.
export default defineConfig({
  publicDir: false,
  base: './',
  define: { 'import.meta.env.VITE_STANDALONE': JSON.stringify('true') },
  plugins: [
    react(),
    {
      name: 'standalone-modern-font-format',
      enforce: 'pre',
      transform(code, id) {
        if (id.includes('@fontsource/') && id.endsWith('.css')) {
          // Modern browsers support WOFF2. Do not embed duplicate WOFF fallbacks.
          return code.replace(/,\s*url\([^)]*\.woff\)\s*format\(['"]woff['"]\)/g, '');
        }
      },
    },
    {
      name: 'standalone-document-metadata',
      transformIndexHtml(html) {
        return html
          .replace('href="/favicon.svg"', `href="data:image/svg+xml,${encodeURIComponent(favicon)}"`)
          .replace('<title>QubitYield | The calibration decision</title>', '<title>QubitYield | Offline evidence preview</title>')
          .replace('</head>', `<script type="application/json" id="font-license-notices">${fontNotices}</script></head>`);
      },
    },
    viteSingleFile({ removeViteModuleLoader: true }),
  ],
  build: {
    outDir: 'preview',
    emptyOutDir: true,
    assetsInlineLimit: 100_000_000,
  },
});
