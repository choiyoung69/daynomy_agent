import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Local, same-origin verification: never load the reference project's env or upload sourcemaps.
export default defineConfig({
  envDir: false,
  envPrefix: 'DAYNOMY_FULLWEB_UNCONFIGURED_',
  server: {
    host: '127.0.0.1',
    port: 18082,
    strictPort: true,
    proxy: Object.fromEntries(['/api', '/oauth2', '/login/oauth2'].map(path => [path, { target: 'http://127.0.0.1:18081', changeOrigin: false }])),
  },
  build: { sourcemap: false },
  plugins: [react()],
});
