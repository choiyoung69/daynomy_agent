// Run the reference's decoder functions with a fake request; no server or network.
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { stripTypeScriptTypes } from 'node:module';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = process.argv[2];
if (!output) throw new Error('provide a new output report path');
const apiPath = 'reference/2026-DAYNOMY-dev/frontend/src/features/stocks/api.ts';
const fixturePath = 'knowledge/contracts/stock-search-price.json';
const source = await readFile(path.join(root, apiPath), 'utf8');
const fixture = JSON.parse(await readFile(path.join(root, fixturePath), 'utf8'));
const stripped = stripTypeScriptTypes(source).replace(/^import .*;\s*$/gm, '').replace(/\bexport /g, '');
let response;
let requestPath;
const context = vm.createContext({
  URLSearchParams,
  request: async value => { requestPath = value; return response; }
});
vm.runInContext(stripped + '\nglobalThis.adapters={searchStocks,getLatestStockPrice};', context);
const observations = [];
for (const entry of fixture.cases) {
  response = JSON.parse(entry.body);
  let accepted = true;
  try {
    if (entry.kind === 'price') await context.adapters.getLatestStockPrice(1);
    else if (entry.kind === 'search') await context.adapters.searchStocks('sample');
    else throw new Error('unknown fixture kind');
  } catch { accepted = false; }
  observations.push({ id: entry.id, expected: entry.expected_accept, actual: accepted, passed: accepted === entry.expected_accept });
}
for (const [index, entry] of fixture.request_cases.entries()) {
  response = { stocks: [] };
  await context.adapters.searchStocks(entry.keyword, undefined, entry.country);
  observations.push({ id: `URL${index + 1}`, expected: entry.expected_path, actual: requestPath, passed: requestPath === entry.expected_path });
}
const sourceHashes = {};
for (const relative of [apiPath, fixturePath, 'experiments/knowledge-contracts/stock-decoder.mjs']) {
  sourceHashes[relative] = createHash('sha256').update(await readFile(path.join(root, relative))).digest('hex');
}
const report = {
  checked_at: new Date().toISOString(), runtime: process.version,
  scope: 'Reference web decoder functions and URL generation with fake request; no HTTP/DB/UI or independent evaluation',
  transformation: 'Built-in TypeScript type stripping; request import replaced by fake; export modifiers removed',
  source_hashes: sourceHashes, observations,
  passed: observations.every(entry => entry.passed)
};
await writeFile(path.resolve(root, output), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
console.log(`${report.passed ? 'PASS' : 'FAIL'} reference stock decoder: ${observations.length} cases`);
process.exitCode = report.passed ? 0 : 1;
