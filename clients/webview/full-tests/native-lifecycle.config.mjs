import { defineConfig } from '../fullweb/node_modules/vitest/dist/config.js';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const fromWeb=createRequire(new URL('../fullweb/package.json',import.meta.url));
export default defineConfig({
  root:fileURLToPath(new URL('.',import.meta.url)),
  envDir:false,
  resolve:{alias:[
    {find:/^react$/,replacement:fromWeb.resolve('react')},
    {find:/^react\/jsx-runtime$/,replacement:fromWeb.resolve('react/jsx-runtime')},
    {find:/^react\/jsx-dev-runtime$/,replacement:fromWeb.resolve('react/jsx-dev-runtime')},
    {find:/^react-dom$/,replacement:fromWeb.resolve('react-dom')},
    {find:/^react-dom\/client$/,replacement:fromWeb.resolve('react-dom/client')},
    {find:/^@testing-library\/react$/,replacement:fromWeb.resolve('@testing-library/react')},
    {find:/^vitest$/,replacement:fileURLToPath(new URL('../fullweb/node_modules/vitest/dist/index.js',import.meta.url))},
  ]},
  test:{environment:'jsdom',include:['native-lifecycle.test.tsx'],maxWorkers:1},
});
