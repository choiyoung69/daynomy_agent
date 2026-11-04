import { registerHooks } from 'node:module';
import { fileURLToPath } from 'node:url';
const playwrightURL = new URL('../../../../clients/webview/fullweb/node_modules/playwright/index.mjs', import.meta.url);
registerHooks({ resolve(specifier, context, nextResolve) { return nextResolve(specifier === 'playwright' ? playwrightURL.href : specifier, context); } });
const { chromium } = await import(playwrightURL.href);
const launch = chromium.launch.bind(chromium);
chromium.launch = options => launch({ ...options, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
