import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// The `base` path matters for GitHub Pages. When deploying to
// https://<user>.github.io/<repo>/, set VITE_BASE_PATH to "/<repo>/".
// Locally it defaults to "/" so `npm run dev` just works.
export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [react(), tailwindcss()],
});
