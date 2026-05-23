import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

// Serve the repo's data/ directory at /data/ in dev and copy it into dist/data/
// on build. The pipeline writes data/layout.json; the renderer fetches it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  publicDir: path.resolve(__dirname, '../data'),
});
